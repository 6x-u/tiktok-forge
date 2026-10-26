"""Web (``www.tiktok.com``) signatures and request plumbing.

What actually runs on the wire today:

* ``X-Bogus`` — produced by TikTok's own browser bundle
  (``js/webmssdk.js``, build 1.0.0.417) executed through the node bridge.  The
  Python side never re-implements it: the table rotates every build and a stale
  port silently fails at the edge.
* ``msToken`` — 107 char urlsafe-base64 session token.
* ``ttwid`` — device cookie, provisioned once from bytedance's union register.
* ``verifyFp`` / ``s_v_web_id`` — fingerprinted device id.

``X-Gnarly`` is deliberately *not* emitted: the current bundle has no such
output, so any library that returns one is inventing bytes.  :func:`sign_web`
returns exactly the headers the SDK hands back.
"""

from __future__ import annotations

import base64
import json
import os
import random
import string
import time
import uuid
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional
from urllib.parse import urlencode, urlparse, urlunparse

from tiktokforge.bridge import BridgeError, SignBridge, get_bridge
from tiktokforge.config import WEB_AID, WEB_DEFAULTS, WEB_USER_AGENT, WebDefaults

__all__ = [
    "generate_ms_token",
    "generate_verify_fp",
    "generate_web_id",
    "generate_device_id",
    "generate_x_bogus",
    "sign_web",
    "generate_web_headers",
    "build_query",
    "with_signature",
    "provision_ttwid",
    "WebClient",
    "TTWID_REGISTER_URL",
]

TTWID_REGISTER_URL = "https://ttwid.bytedance.com/ttwid/union/register/"
TIKTOK_HOST = "https://www.tiktok.com"

_URLSAFE = string.ascii_letters + string.digits + "-_"


# ------------------------------------------------------------------ tokens

def generate_ms_token(length: int = 107) -> str:
    """Return an msToken of the current shape (urlsafe base64, 107 chars).

    ``length`` is clamped to a sane window; TikTok's edge checks shape and
    entropy, not a fixed length.
    """
    length = max(48, min(int(length), 160))
    raw = base64.urlsafe_b64encode(os.urandom(96)).decode("ascii").rstrip("=")
    if length <= len(raw):
        return raw[:length]
    pad = "".join(random.choices(_URLSAFE, k=length - len(raw)))
    return raw + pad


def generate_verify_fp(web_id: Optional[str] = None) -> str:
    """Return a ``verify_...`` fingerprint in the shape the web app writes to
    ``s_v_web_id``."""
    wid = web_id or generate_web_id()
    seed = int(time.time() * 1000)
    head = format(seed, "x")[-9:]
    tail = base64.b32encode(os.urandom(6)).decode("ascii").rstrip("=").lower()[:10]
    return f"verify_l{head}_{wid[-8:]}_{tail[:4]}_{tail[4:8]}_{wid[:4]}"


def generate_web_id() -> str:
    """19 digit web id (``tt_webid`` / ``webId``)."""
    return str(random.randint(10**18, 10**19 - 1))


def generate_device_id() -> str:
    return generate_web_id()


# ----------------------------------------------------------------- signing

def _as_full_url(url: str, host: str = TIKTOK_HOST) -> str:
    text = str(url or "")
    if not text:
        raise ValueError("url is empty")
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("/"):
        return host + text
    return f"{host}/{text}"


def build_query(params: Mapping[str, Any], base: Optional[Mapping[str, Any]] = None) -> str:
    """Merge ``base`` with ``params`` and render a query string."""
    merged: Dict[str, str] = {}
    if base:
        merged.update({str(k): str(v) for k, v in base.items()})
    for key, value in params.items():
        if value is None:
            continue
        merged[str(key)] = "true" if value is True else "false" if value is False else str(value)
    return urlencode(merged)


def sign_web(
    url: str,
    *,
    user_agent: Optional[str] = None,
    body: Optional[str] = None,
    referer: str = "https://www.tiktok.com/",
    cookie: Optional[str] = None,
    aid: int = WEB_AID,
    bridge: Optional[SignBridge] = None,
) -> Dict[str, str]:
    """Sign a URL with the vendored bundle.  Returns ``{"X-Bogus": ...}``."""
    full = _as_full_url(url)
    engine = bridge or get_bridge()
    return engine.sign(
        full,
        referer=referer,
        body=body,
        cookie=cookie,
        user_agent=user_agent or WEB_USER_AGENT,
        aid=aid,
    )


def generate_x_bogus(
    url_params: str,
    user_agent: str = "",
    ts: Optional[int] = None,
    *,
    referer: str = "https://www.tiktok.com/",
    bridge: Optional[SignBridge] = None,
) -> str:
    """Return the real ``X-Bogus`` for a query string or full URL.

    ``ts`` is accepted for backwards compatibility and ignored: the bundle
    stamps the current time itself, and a forced timestamp makes the signature
    stale at the edge.
    """
    headers = sign_web(
        url_params,
        user_agent=user_agent or WEB_USER_AGENT,
        referer=referer,
        bridge=bridge,
    )
    for key, value in headers.items():
        if key.lower() == "x-bogus":
            return value
    raise BridgeError(f"bundle returned no X-Bogus: {headers!r}")


def with_signature(
    url: str,
    *,
    user_agent: Optional[str] = None,
    referer: str = "https://www.tiktok.com/",
    cookie: Optional[str] = None,
    param: str = "X-Bogus",
    bridge: Optional[SignBridge] = None,
) -> str:
    """Return ``url`` with the signature appended as a query parameter."""
    headers = sign_web(
        url, user_agent=user_agent, referer=referer, cookie=cookie, bridge=bridge
    )
    value = headers.get(param) or headers.get(param.lower()) or headers.get(param.upper())
    if not value:
        raise BridgeError(f"no {param} in {sorted(headers)}")
    sep = "&" if "?" in url else "?"
    if url.endswith("?") or url.endswith("&"):
        sep = ""
    return f"{url}{sep}{param}={value}"


# ----------------------------------------------------------------- headers

def generate_web_headers(
    url_params: str,
    user_agent: Optional[str] = None,
    referer: str = "https://www.tiktok.com/",
    ts: Optional[int] = None,
    *,
    cookie: Optional[str] = None,
    web_id: Optional[str] = None,
    ms_token: Optional[str] = None,
    bridge: Optional[SignBridge] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Full header set for a signed web call."""
    ua = user_agent or WEB_USER_AGENT
    wid = web_id or generate_web_id()
    token = ms_token or generate_ms_token()

    headers: Dict[str, str] = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Origin": "https://www.tiktok.com",
        "sec-ch-ua": '"Chromium";v="141", "Google Chrome";v="141", "Not?A_Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    headers.update(sign_web(url_params, user_agent=ua, referer=referer, cookie=cookie, bridge=bridge))
    headers["Cookie"] = cookie or (
        f"msToken={token}; tt_webid={wid}; tt_webid_v2={wid}; "
        f"s_v_web_id={generate_verify_fp(wid)}"
    )
    if extra:
        headers.update({str(k): str(v) for k, v in extra.items()})
    return headers


# ------------------------------------------------------------------ cookies

def provision_ttwid(
    session: Any = None,
    *,
    timeout: float = 20.0,
    user_agent: str = WEB_USER_AGENT,
) -> str:
    """Fetch a real ``ttwid`` cookie from bytedance's union register.

    Works with a :class:`requests.Session`; when ``session`` is omitted a throw
    away session is used and only the cookie value is returned.
    """
    import requests

    own = session is None
    s = session or requests.Session()
    try:
        payload = {
            "region": "va",
            "aid": 1768,
            "needFid": False,
            "service": "www.tiktok.com",
            "migrate_info": {"ticket": "", "source": "node"},
            "cbUrlProtocol": "https",
            "union": True,
        }
        s.post(
            TTWID_REGISTER_URL,
            json=payload,
            headers={
                "User-Agent": user_agent,
                "Content-Type": "application/json",
                "Origin": "https://www.tiktok.com",
                "Referer": "https://www.tiktok.com/",
            },
            timeout=timeout,
        )
        jar = getattr(s, "cookies", None)
        if jar is not None:
            value = jar.get("ttwid")
            if value:
                return value
        resp = s.get(TIKTOK_HOST, headers={"User-Agent": user_agent}, timeout=timeout)
        return resp.cookies.get("ttwid", "") or s.cookies.get("ttwid", "")  # type: ignore[union-attr]
    finally:
        if own:
            s.close()


# ------------------------------------------------------------------- client

class WebClient:
    """A ``requests`` session that signs every call it makes.

    >>> c = WebClient()
    >>> c.get("/api/post/item_list/", params={"count": 20, "cursor": 0})
    <Response [200]>

    The signature is recomputed per request (fresh timestamp), and any 200-with-
    empty-body response is retried once with a new signature before it is handed
    back, because that is exactly how TikTok signals a stale one.
    """

    def __init__(
        self,
        *,
        user_agent: str = WEB_USER_AGENT,
        referer: str = "https://www.tiktok.com/",
        defaults: Optional[WebDefaults] = None,
        cookie: Optional[str] = None,
        proxies: Optional[Mapping[str, str]] = None,
        retries: int = 2,
        timeout: float = 25.0,
        bridge: Optional[SignBridge] = None,
        sign_body: bool = True,
    ) -> None:
        import requests

        self.session = requests.Session()
        self.user_agent = user_agent
        self.referer = referer
        self.defaults = defaults or WEB_DEFAULTS
        self.retries = max(0, int(retries))
        self.timeout = timeout
        self.bridge = bridge
        self.sign_body = sign_body
        self._explicit_cookie = cookie

        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": referer,
                "Origin": "https://www.tiktok.com",
            }
        )
        if proxies:
            self.session.proxies.update(dict(proxies))
        if cookie:
            self.session.headers["Cookie"] = cookie

    # -- housekeeping -------------------------------------------------

    def bootstrap(self, timeout: Optional[float] = None) -> str:
        """Prime cookies (ttwid and friends) with a plain homepage hit."""
        resp = self.session.get(
            TIKTOK_HOST + "/",
            timeout=timeout or self.timeout,
            headers={"User-Agent": self.user_agent},
        )
        return resp.cookies.get("ttwid", "") or ""

    @property
    def cookie_string(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self.session.cookies)

    def ensure_ms_token(self) -> str:
        token = self.session.cookies.get("msToken")
        if token:
            return token
        token = generate_ms_token()
        self.session.cookies.set("msToken", token, domain=".tiktok.com")
        return token

    # -- url building -------------------------------------------------

    def _build_url(self, path_or_url: str, params: Optional[Mapping[str, Any]]) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            full = path_or_url
        elif path_or_url.startswith("/"):
            full = TIKTOK_HOST + path_or_url
        else:
            full = f"{TIKTOK_HOST}/{path_or_url}"
        merged: Dict[str, Any] = dict(self.defaults.as_params())
        if params:
            merged.update({k: v for k, v in params.items() if v is not None})
        if "?" in full:
            head, _, tail = full.partition("?")
            existing = tail.split("&") if tail else []
            query = "&".join(existing + [build_query(merged)])
            return f"{head}?{query}"
        return f"{full}?{build_query(merged)}"

    # -- request ------------------------------------------------------

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Optional[Any] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        **kwargs: Any,
    ) -> Any:
        method = method.upper()
        body_text: Optional[str] = None
        if data is not None and not isinstance(data, (bytes, bytearray)):
            body_text = data if isinstance(data, str) else urlencode(data)
        elif json_body is not None:
            body_text = json.dumps(json_body, separators=(",", ":"))

        attempt = 0
        last = None
        while attempt <= self.retries:
            attempt += 1
            url = self._build_url(path_or_url, params)
            signed = sign_web(
                url,
                user_agent=self.user_agent,
                body=body_text if self.sign_body else None,
                referer=self.referer,
                cookie=self.cookie_string or self._explicit_cookie,
                bridge=self.bridge,
            )
            hdrs: Dict[str, str] = dict(signed)
            if headers:
                hdrs.update({str(k): str(v) for k, v in headers.items()})
            send_kwargs = dict(kwargs)
            send_kwargs.setdefault("timeout", self.timeout)
            if body_text is not None:
                send_kwargs["data"] = body_text.encode("utf-8")
            resp = self.session.request(method, url, headers=hdrs, **send_kwargs)
            last = resp
            if resp.status_code == 200 and resp.content not in (b"", b"{}"):
                return resp
            if resp.status_code not in (200, 429) and resp.status_code < 500:
                return resp
            time.sleep(min(0.4 * attempt, 1.2))
        return last

    def get(self, path_or_url: str, **kwargs: Any) -> Any:
        return self.request("GET", path_or_url, **kwargs)

    def post(self, path_or_url: str, **kwargs: Any) -> Any:
        return self.request("POST", path_or_url, **kwargs)

    def json(self, path_or_url: str, **kwargs: Any) -> Any:
        resp = self.get(path_or_url, **kwargs)
        try:
            return resp.json()
        except Exception:
            return None

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "WebClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
