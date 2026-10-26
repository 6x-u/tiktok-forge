"""Node bridge for the vendored TikTok web SDK.

The browser bundle that TikTok ships (``js/webmssdk.js``) is the only thing
that produces signatures the edge actually accepts today.  Re-implementing it
in Python is a losing race: every build rotates the tables.  So this module
runs the real bundle instead, inside a small browser shim, and talks to it over
a pipe.

One node process is started lazily and reused for every signature.  Booting the
context costs a couple of hundred milliseconds; a signature after that costs
well under a millisecond.

    from tiktokforge.bridge import get_bridge
    get_bridge().sign("https://www.tiktok.com/api/post/item_list/?aid=1988")

If node cannot be found, :class:`NodeUnavailable` is raised with the places that
were searched.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "NodeUnavailable",
    "BridgeError",
    "SignBridge",
    "get_bridge",
    "find_node",
    "sign_url",
]

_JS_DIR = Path(__file__).resolve().parent / "js"
_SERVER = _JS_DIR / "sign_server.js"
_BUNDLE = _JS_DIR / "webmssdk.js"


class NodeUnavailable(RuntimeError):
    """Raised when no usable JavaScript runtime is present."""


class BridgeError(RuntimeError):
    """Raised when the signing server fails a request."""


def _candidate_nodes() -> Iterable[Path]:
    env = os.environ.get("TIKTOKFORGE_NODE") or os.environ.get("TT_NODE")
    if env:
        yield Path(env)
    which = shutil.which("node")
    if which:
        yield Path(which)
    if sys.platform == "win32":
        roots = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs",
            Path(r"C:\Program Files (x86)\nodejs"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs",
            Path(os.environ.get("APPDATA", "")) / "npm",
            Path(os.environ.get("USERPROFILE", "")) / "scoop" / "apps" / "nodejs" / "current",
        ]
        for root in roots:
            yield root / "node.exe"
    else:
        for p in ("/usr/local/bin/node", "/usr/bin/node", "/opt/homebrew/bin/node", "/snap/bin/node"):
            yield Path(p)
    # runtimes bundled next to this interpreter (CI, agent sandboxes)
    for base in (Path(sys.executable).resolve().parent, Path(__file__).resolve().parents[3]):
        for pattern in ("**/node/bin/node.exe", "**/node/bin/node", "**/node.exe"):
            try:
                for hit in base.glob(pattern):
                    yield hit
            except (OSError, ValueError):
                continue


def find_node(extra: Optional[str] = None) -> str:
    """Return the path to a node binary, or raise :class:`NodeUnavailable`."""
    checked: List[str] = []
    if extra:
        checked.append(extra)
        if Path(extra).is_file():
            return extra
    for cand in _candidate_nodes():
        try:
            text = str(cand)
        except Exception:  # pragma: no cover - defensive
            continue
        if not text or text in checked:
            continue
        checked.append(text)
        p = Path(text)
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        return str(p)
    raise NodeUnavailable(
        "no JavaScript runtime found.  Install Node.js 16+ (https://nodejs.org) "
        "or point TIKTOKFORGE_NODE at the binary.\nsearched:\n  " + "\n  ".join(checked)
    )


class SignBridge:
    """A long-lived ``sign_server.js`` process speaking JSON lines."""

    def __init__(
        self,
        node: Optional[str] = None,
        *,
        user_agent: Optional[str] = None,
        cookie: str = "",
        aid: int = 1988,
        boot_timeout: float = 45.0,
        call_timeout: float = 20.0,
    ) -> None:
        self.node = find_node(node)
        self.user_agent = user_agent or _default_user_agent()
        self.cookie = cookie
        self.aid = int(aid)
        self.boot_timeout = boot_timeout
        self.call_timeout = call_timeout

        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._seq = 0
        self._boots = 0

    # ------------------------------------------------------------------ boot

    def _spawn(self) -> None:
        if not _SERVER.is_file():
            raise NodeUnavailable(f"missing signing server: {_SERVER}")
        if not _BUNDLE.is_file():
            raise NodeUnavailable(f"missing vendored bundle: {_BUNDLE}")
        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [self.node, str(_SERVER), "--bundlePath", str(_BUNDLE), "--userAgent", self.user_agent],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(_JS_DIR),
            **kwargs,
        )
        line = _readline(proc, self.boot_timeout)
        if not line:
            err = ""
            try:
                err = (proc.stderr.read() or "")[-800:] if proc.stderr else ""
            except Exception:
                pass
            proc.kill()
            raise BridgeError(f"signing server did not boot: {err.strip()}")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            proc.kill()
            raise BridgeError(f"bad boot line: {line[:300]!r}") from exc
        if not msg.get("ok"):
            proc.kill()
            raise BridgeError(f"signing server failed to boot: {msg.get('error')}")
        self._proc = proc
        self._boots += 1
        # prime the engine so the first real signature is warm
        try:
            self._call({"op": "warm"}, timeout=self.boot_timeout)
        except BridgeError:
            pass

    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._spawn()
        assert self._proc is not None
        return self._proc

    # ------------------------------------------------------------------ call

    def _call(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Any:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            proc = self._ensure()
        self._seq += 1
        payload = dict(payload, id=self._seq)
        assert proc.stdin is not None
        try:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.close()
            raise BridgeError("signing server pipe closed") from exc
        line = _readline(proc, timeout or self.call_timeout)
        if not line:
            self.close()
            raise BridgeError("signing server returned nothing")
        msg = json.loads(line)
        if not msg.get("ok"):
            raise BridgeError(str(msg.get("error") or "unknown signing error"))
        return msg.get("data")

    # ------------------------------------------------------------------ api

    def sign(
        self,
        url: str,
        *,
        referer: Optional[str] = None,
        body: Optional[str] = None,
        cookie: Optional[str] = None,
        user_agent: Optional[str] = None,
        aid: Optional[int] = None,
    ) -> Dict[str, str]:
        """Sign one request URL.  Returns the headers the SDK produces."""
        payload: Dict[str, Any] = {
            "op": "sign",
            "url": url,
            "aid": int(aid if aid is not None else self.aid),
            "cookie": cookie if cookie is not None else self.cookie,
        }
        if referer:
            payload["referer"] = referer
        if body:
            payload["body"] = body
        if user_agent:
            payload["userAgent"] = user_agent
        with self._lock:
            data = self._call(payload)
        if not isinstance(data, dict):
            raise BridgeError(f"unexpected signing payload: {data!r}")
        return {str(k): str(v) for k, v in data.items()}

    def sign_many(self, urls: Iterable[str], **kwargs: Any) -> List[Dict[str, str]]:
        with self._lock:
            return [self.sign(u, **kwargs) for u in urls]

    def info(self) -> Dict[str, Any]:
        with self._lock:
            return self._call({"op": "info"}) or {}

    def ping(self) -> bool:
        with self._lock:
            try:
                return bool(self._call({"op": "ping"}, timeout=5).get("pong"))
            except BridgeError:
                return False

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None and proc.stdin:
                proc.stdin.write(json.dumps({"op": "quit", "id": 0}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=3)
        except Exception:
            pass
        finally:
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

    # context manager / lifecycle
    def __enter__(self) -> "SignBridge":
        self._ensure()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @property
    def boot_count(self) -> int:
        return self._boots


def _default_user_agent() -> str:
    try:
        from tiktokforge.config import WEB_USER_AGENT

        return WEB_USER_AGENT
    except Exception:  # pragma: no cover
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        )


def _readline(proc: subprocess.Popen, timeout: float) -> str:
    """Read one line from ``proc.stdout`` without hanging forever."""
    out = proc.stdout
    if out is None:
        return ""
    result: List[str] = []

    def reader() -> None:
        try:
            result.append(out.readline())
        except Exception:
            result.append("")

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return ""
    return result[0].strip() if result else ""


_br: Optional[SignBridge] = None
_br_lock = threading.Lock()


def get_bridge(**kwargs: Any) -> SignBridge:
    """Return the process-wide bridge, creating it on first use."""
    global _br
    with _br_lock:
        if _br is None:
            _br = SignBridge(**kwargs)
            atexit.register(_br.close)
        return _br


def sign_url(url: str, **kwargs: Any) -> Dict[str, str]:
    """Convenience wrapper around :func:`get_bridge`."""
    return get_bridge().sign(url, **kwargs)
