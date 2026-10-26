

from __future__ import annotations

import gzip
import json
from random import choice
from time import time
from typing import Any, Dict, Mapping, Optional, Union

from tiktokforge.algorithms.argus import Argus
from tiktokforge.algorithms.gorgon import Gorgon
from tiktokforge.algorithms.ladon import Ladon
from tiktokforge.algorithms.protobuf import ProtoBuf, protobuf_decode, protobuf_encode
from tiktokforge.algorithms.stub import generate_stub
from tiktokforge.algorithms.ttencrypt import TTEncrypt
from tiktokforge.config import APP_DEFAULTS, APP_AID, AppDefaults, version_code_for

__all__ = ["TikTokSigner", "generate_headers", "encrypt", "decrypt", "encode", "decode"]

Params = Union[str, Mapping[str, Any]]


def _params_str(params: Params) -> str:
    if isinstance(params, str):
        return params
    return "&".join(f"{k}={v}" for k, v in params.items() if v is not None)


def _body_bytes(data: Union[str, bytes, Mapping[str, Any], None]) -> Optional[bytes]:
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode()
    return "&".join(f"{k}={v}" for k, v in data.items()).encode()


class TikTokSigner:
    """Header factory for ``api*.tiktokv.com`` / ``*.tiktokv.com`` endpoints."""

    DEFAULT_AID: int = APP_AID
    DEFAULT_LC_ID: int = APP_DEFAULTS.lc_id
    DEFAULT_SDK_VER: str = APP_DEFAULTS.sdk_ver
    DEFAULT_SDK_VER_CODE: int = APP_DEFAULTS.sdk_ver_code
    DEFAULT_VERSION_NAME: str = APP_DEFAULTS.version_name
    DEFAULT_VERSION_CODE: int = APP_DEFAULTS.version_code

    _encryptor: Optional[TTEncrypt] = None

    # ------------------------------------------------------------------ setup

    @classmethod
    def _get_encryptor(cls) -> TTEncrypt:
        if cls._encryptor is None:
            cls._encryptor = TTEncrypt()
        return cls._encryptor

    @classmethod
    def configure(cls, profile: AppDefaults) -> None:
        """Point the defaults at another app build / device."""
        cls.DEFAULT_AID = profile.aid
        cls.DEFAULT_LC_ID = profile.lc_id
        cls.DEFAULT_SDK_VER = profile.sdk_ver
        cls.DEFAULT_SDK_VER_CODE = profile.sdk_ver_code
        cls.DEFAULT_VERSION_NAME = profile.version_name
        cls.DEFAULT_VERSION_CODE = profile.version_code

    # ------------------------------------------------------------------ trace

    @staticmethod
    def _trace(device_id: Optional[str], aid: int, ticket: float) -> str:
        if device_id:
            try:
                device_hex = hex(int(device_id))[2:]
            except ValueError:
                device_hex = str(device_id).lower()
            return device_hex + "".join(choice("0123456789abcdef") for _ in range(2)) + "0" + hex(aid)[2:]
        return (
            str("%x" % (round(ticket * 1000) & 0xFFFFFFFF))
            + "10"
            + "".join(choice("0123456789abcdef") for _ in range(16))
        )

    # ----------------------------------------------------------------- headers

    @classmethod
    def generate_headers(
        cls,
        params: Params,
        data: Optional[Union[str, bytes, Mapping[str, Any]]] = None,
        device_id: Optional[str] = None,
        aid: Union[str, int] = APP_DEFAULTS.aid,
        lc_id: Union[str, int] = APP_DEFAULTS.lc_id,
        sdk_ver: str = APP_DEFAULTS.sdk_ver,
        sdk_ver_code: Union[str, int] = APP_DEFAULTS.sdk_ver_code,
        version_name: str = APP_DEFAULTS.version_name,
        version_code: Optional[Union[str, int]] = None,
        cookie: Optional[str] = None,
        unix: Optional[int] = None,
        profile: Optional[AppDefaults] = None,
    ) -> Dict[str, str]:
        if profile is not None:
            aid, lc_id = profile.aid, profile.lc_id
            sdk_ver, sdk_ver_code = profile.sdk_ver, profile.sdk_ver_code
            version_name = profile.version_name
            device_id = device_id or profile.device.device_id
        aid = int(aid)
        lc_id = int(lc_id)
        sdk_ver_code = int(sdk_ver_code)
        if version_code is None:
            version_code = version_code_for(version_name)
        version_code = int(version_code)

        ticket = time() if unix is None else float(unix)
        unix_value = int(ticket)

        params_str = _params_str(params)
        body = _body_bytes(data)

        trace = cls._trace(device_id, aid, ticket)
        headers: Dict[str, str] = {
            "x-ss-req-ticket": str(int(time() * 1000)),
            "x-tt-trace-id": f"00-{trace}-{trace[:16]}-01",
        }
        if body is not None:
            headers["x-ss-stub"] = generate_stub(data=body)

        headers.update(Ladon.encrypt(aid=aid, lc_id=lc_id, unix=unix_value))
        headers.update(
            Gorgon.encrypt(params=params_str, headers=headers, cookie=cookie, unix=unix_value)
        )
        headers.update(
            Argus.encrypt(
                params=params_str,
                data=body,
                unix=unix_value,
                aid=aid,
                lc_id=lc_id,
                device_id=device_id,
                sdk_ver=sdk_ver,
                sdk_ver_code=sdk_ver_code,
                version_name=version_name,
                version_code=version_code,
            )
        )
        if cookie is not None:
            headers["cookie"] = cookie
        return headers

    # ------------------------------------------------------------- payloads

    @classmethod
    def encrypt(
        cls,
        data: Union[str, bytes, Mapping[str, Any]],
        *,
        compress: bool = True,
        compress_level: int = 9,
    ) -> bytes:
        """Encrypt a device-register payload the way the app does.

        The app gzips the protobuf body first (the cipher stamps a gzip header
        over the plaintext), so ``compress=False`` only exists for raw blobs.
        """
        if isinstance(data, Mapping):
            data = json.dumps(data, separators=(",", ":")).encode()
        elif isinstance(data, str):
            data = data.encode()
        if compress:
            data = gzip.compress(data, compresslevel=compress_level, mtime=0)
        return cls._get_encryptor().encrypt(data)

    @classmethod
    def decrypt(cls, data: bytes) -> str:
        return cls._get_encryptor().decrypt(data)

    @classmethod
    def encode(cls, data: Dict) -> bytes:
        return protobuf_encode(data=data)

    @classmethod
    def decode(cls, data: Union[bytes, ProtoBuf]) -> Dict:
        return protobuf_decode(data=data)


def generate_headers(
    params: Params,
    data: Optional[Union[str, bytes, Mapping[str, Any]]] = None,
    device_id: str = "",
    aid: Union[int, str] = APP_DEFAULTS.aid,
    lc_id: Union[int, str] = APP_DEFAULTS.lc_id,
    sdk_ver: str = APP_DEFAULTS.sdk_ver,
    sdk_ver_code: Union[int, str] = APP_DEFAULTS.sdk_ver_code,
    version_name: str = APP_DEFAULTS.version_name,
    version_code: Optional[Union[int, str]] = None,
    cookie: Optional[str] = None,
    unix: Optional[int] = None,
    profile: Optional[AppDefaults] = None,
) -> Dict[str, str]:
    return TikTokSigner.generate_headers(
        params=params,
        data=data,
        device_id=device_id or None,
        aid=aid,
        lc_id=lc_id,
        sdk_ver=sdk_ver,
        sdk_ver_code=sdk_ver_code,
        version_name=version_name,
        version_code=version_code,
        cookie=cookie,
        unix=unix,
        profile=profile,
    )


def encrypt(data: Union[str, bytes, Dict]) -> bytes:
    return TikTokSigner.encrypt(data)


def decrypt(data: bytes) -> str:
    return TikTokSigner.decrypt(data)


def encode(data: Dict) -> bytes:
    return TikTokSigner.encode(data=data)


def decode(data: Union[bytes, ProtoBuf]) -> Dict:
    return TikTokSigner.decode(data=data)
