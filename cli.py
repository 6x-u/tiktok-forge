
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

DEFAULT_PATH = "/api/challenge/detail/"
DEFAULT_PARAMS = "aid=1988&challengeName=fyp"


def _params_dict(query: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for chunk in query.split("&"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            out[key] = value
    return out


def run(path: str, params: str, *, net: bool) -> Dict[str, Any]:
    from tiktokforge import __version__
    from tiktokforge.bridge import find_node, get_bridge
    from tiktokforge.web import WebClient, generate_web_headers

    report: Dict[str, Any] = {"ok": False, "library": __version__}

    try:
        report["node"] = find_node()
    except Exception as exc:  # noqa: BLE001 - report, do not raise
        report["error"] = f"no node runtime: {exc}"
        return report

    bridge = get_bridge()
    try:
        report["bundle"] = (bridge.info() or {}).get("bundle")
    finally:
        bridge.close()

    url = f"https://www.tiktok.com{path}?{params}"
    headers = generate_web_headers(url)
    report["x_bogus"] = headers.get("X-Bogus")
    report["cookies"] = sorted(
        part.split("=", 1)[0] for part in headers.get("Cookie", "").split("; ") if part
    )
    if not report["x_bogus"]:
        report["error"] = "no signature produced"
        return report

    if not net:
        report["ok"] = True
        return report

    client = WebClient(retries=1)
    try:
        response = client.get(f"https://www.tiktok.com{path}", params=_params_dict(params))
        report["status"] = response.status_code
        report["bytes"] = len(response.content)
        try:
            payload = response.json()
        except ValueError:
            report["error"] = "non-json body"
            return report
        if isinstance(payload, dict) and "challengeInfo" in payload:
            stats = payload["challengeInfo"]["challenge"].get("stats", {})
            report["video_count"] = stats.get("videoCount")
            report["ok"] = True
        else:
            report["error"] = "unexpected payload shape"
    finally:
        client.close()
    return report


def _print_report(report: Dict[str, Any]) -> None:
    print(f"library      {report.get('library')}")
    print(f"node         {report.get('node')}")
    print(f"bundle       {report.get('bundle')}")
    print(f"X-Bogus      {report.get('x_bogus')}")
    print(f"cookies      {', '.join(report.get('cookies') or [])}")
    if "status" in report:
        print(f"status       {report['status']}  ({report.get('bytes')} bytes)")
    if "video_count" in report:
        print(f"video count  {report['video_count']}")
    if report.get("ok"):
        print("result       OK")
    else:
        print(f"result       FAILED: {report.get('error')}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tiktokforge-verify",
        description="sign a live TikTok URL and report whether the edge accepts it",
    )
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument("--no-net", action="store_true", help="skip the HTTP call")
    parser.add_argument("--path", default=DEFAULT_PATH, help=f"endpoint (default {DEFAULT_PATH})")
    parser.add_argument("--params", default=DEFAULT_PARAMS, help="query string to sign")
    args = parser.parse_args(argv)

    try:
        report = run(args.path, args.params, net=not args.no_net)
    except Exception as exc:  # noqa: BLE001 - CLI surface
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
