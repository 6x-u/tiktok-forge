"""Version tables, device profiles and web request defaults.

Everything that TikTok rotates on a release is kept here so an update is a
single edit instead of a hunt through the algorithms.

``version_code`` is derived from the human version with the scheme TikTok has
used since 5.x::

    2023 7 00 04 0
    |    | |  |  |
    year | minor patch trailing zero
         major % 10

so ``37.0.4 -> 2023700040`` and ``47.5.3 -> 2023705030``.  Some releases ship a
code that does not follow the pattern; those live in :data:`VERSION_CODE_OVERRIDES`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, Optional

__all__ = [
    "WEB_USER_AGENT",
    "WEB_AID",
    "APP_AID",
    "AID_MUSICAL_LY",
    "AID_TIKTOK",
    "version_code_for",
    "VERSION_CODE_OVERRIDES",
    "WebDefaults",
    "AppDefaults",
    "DeviceProfile",
    "WEB_DEFAULTS",
    "APP_DEFAULTS",
]

# --------------------------------------------------------------------- aid

APP_AID = 1233
AID_MUSICAL_LY = 1233
AID_TIKTOK = 2329
WEB_AID = 1988

# ------------------------------------------------------------------ agents

WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

APP_USER_AGENT_TEMPLATE = (
    "com.zhiliaoapp.musically/{version_code} (Linux; U; Android {os_version}; "
    "{language}_{region}; {device_type}; Build/{build};tt-ok/3.12.13.4-tiktok)"
)

# ---------------------------------------------------------------- versions

#: Version pairs that do not follow the default derivation.
VERSION_CODE_OVERRIDES: Dict[str, int] = {
    "37.0.4": 2023700040,
    "47.5.3": 2023705030,
}


def version_code_for(version_name: str) -> int:
    """Return TikTok's numeric ``version_code`` for a ``major.minor.patch`` string."""
    text = str(version_name).strip()
    if not text:
        raise ValueError("version_name is empty")
    if text in VERSION_CODE_OVERRIDES:
        return VERSION_CODE_OVERRIDES[text]
    parts = text.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError as exc:
        raise ValueError(f"bad version string: {version_name!r}") from exc
    return int(f"2023{major % 10}{minor:02d}{patch:02d}0")


# ------------------------------------------------------------------- web

@dataclass(frozen=True)
class WebDefaults:
    """Query defaults for www.tiktok.com API calls."""

    aid: int = WEB_AID
    app_name: str = "tiktok_web"
    device_platform: str = "web_pc"
    channel: str = "tiktok_web"
    app_language: str = "en"
    language: str = "en"
    region: str = "US"
    priority_region: str = ""
    browser_language: str = "en-US"
    browser_platform: str = "Win32"
    browser_name: str = "Mozilla"
    browser_version: str = "5.0 (Windows)"
    browser_online: bool = True
    cookie_enabled: bool = True
    screen_width: int = 1920
    screen_height: int = 1080
    os: str = "windows"
    tz_name: str = "UTC"
    is_fullscreen: bool = False
    is_page_visible: bool = True
    focus_state: bool = True
    history_len: int = 3
    referer: str = ""
    user_agent: str = WEB_USER_AGENT

    def as_params(self, **overrides: object) -> Dict[str, str]:
        base = {
            "aid": str(self.aid),
            "app_language": self.app_language,
            "app_name": self.app_name,
            "browser_language": self.browser_language,
            "browser_name": self.browser_name,
            "browser_online": "true" if self.browser_online else "false",
            "browser_platform": self.browser_platform,
            "browser_version": self.browser_version,
            "channel": self.channel,
            "cookie_enabled": "true" if self.cookie_enabled else "false",
            "device_platform": self.device_platform,
            "focus_state": "true" if self.focus_state else "false",
            "history_len": str(self.history_len),
            "is_fullscreen": "true" if self.is_fullscreen else "false",
            "is_page_visible": "true" if self.is_page_visible else "false",
            "language": self.language,
            "os": self.os,
            "priority_region": self.priority_region,
            "referer": self.referer,
            "region": self.region,
            "screen_height": str(self.screen_height),
            "screen_width": str(self.screen_width),
            "tz_name": self.tz_name,
        }
        for key, value in overrides.items():
            if value is None:
                continue
            base[str(key)] = str(value).lower() if isinstance(value, bool) else str(value)
        return base


WEB_DEFAULTS = WebDefaults()


# ------------------------------------------------------------------- app

@dataclass(frozen=True)
class DeviceProfile:
    """An Android build identity, matched to the UA and the signatures."""

    device_id: str = "0"
    install_id: str = "0"
    device_type: str = "Pixel 7"
    device_brand: str = "google"
    os_version: str = "14"
    os_api: int = 34
    cpu_abi: str = "arm64-v8a"
    build: str = "UP1A.231005.007"
    language: str = "en"
    region: str = "US"
    channel: str = "googleplay"
    timezone: int = 0


@dataclass(frozen=True)
class AppDefaults:
    """Android app identity + SDK version used when signing app requests."""

    aid: int = APP_AID
    app_name: str = "musical_ly"
    package: str = "com.zhiliaoapp.musically"
    version_name: str = "47.5.3"
    sdk_ver: str = "v05.01.03-ov-android"
    sdk_ver_code: int = 83952160
    lc_id: int = 2142840551
    device: DeviceProfile = field(default_factory=DeviceProfile)

    @property
    def version_code(self) -> int:
        return version_code_for(self.version_name)

    def user_agent(self) -> str:
        return APP_USER_AGENT_TEMPLATE.format(
            version_code=self.version_code,
            os_version=self.device.os_version,
            language=self.device.language,
            region=self.device.region,
            device_type=self.device.device_type,
            build=self.device.build,
        )

    def with_version(self, version_name: str, version_code: Optional[int] = None) -> "AppDefaults":
        import dataclasses

        return dataclasses.replace(
            self,
            version_name=version_name,
            sdk_ver_code=self.sdk_ver_code if version_code is None else self.sdk_ver_code,
        )


APP_DEFAULTS = AppDefaults()
