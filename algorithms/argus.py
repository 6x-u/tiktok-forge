from typing import Dict, Optional, Union
from urllib.parse import parse_qs, urlencode
from hashlib import md5
from struct import unpack
from random import randint
from base64 import b64encode
from time import time
from uuid import uuid4

from Crypto.Util.Padding import pad
from Crypto.Cipher.AES import MODE_CBC, block_size, new

from tiktokforge.algorithms.protobuf import ProtoBuf
from tiktokforge.algorithms.simon import Simon
from tiktokforge.algorithms.sm3 import SM3
from tiktokforge.algorithms.stub import generate_stub
from tiktokforge.config import APP_AID, APP_DEFAULTS, version_code_for


class Argus:
    _simon = Simon()
    _sm3 = SM3()

    DEFAULT_AID: int = APP_AID
    DEFAULT_LC_ID: int = APP_DEFAULTS.lc_id
    DEFAULT_SDK_VER: str = APP_DEFAULTS.sdk_ver
    DEFAULT_SDK_VER_CODE: int = APP_DEFAULTS.sdk_ver_code
    DEFAULT_APP_VER: str = APP_DEFAULTS.version_name
    DEFAULT_VERSION_CODE: int = APP_DEFAULTS.version_code
    DEFAULT_CHANNEL: str = "googleplay"
    DEFAULT_DEVICE_TYPE: str = "unknown"
    DEFAULT_OS_VERSION: str = "14"

    @staticmethod
    def _encrypt_enc_pb(data: bytes, length: int) -> bytes:
        data_list = list(data)
        xor_array = data_list[:8]
        for i in range(8, length):
            data_list[i] ^= xor_array[i % 8]
        return bytes(data_list[::-1])

    @staticmethod
    def _get_bodyhash(stub: Optional[str] = None) -> bytes:
        if stub is None or len(stub) == 0:
            return Argus._sm3.encrypt(bytes(16))[0:6]
        return Argus._sm3.encrypt(bytes.fromhex(stub))[0:6]

    @staticmethod
    def _get_queryhash(query: str) -> bytes:
        if query is None or len(query) == 0:
            return Argus._sm3.encrypt(bytes(16))[0:6]
        return Argus._sm3.encrypt(query.encode())[0:6]

    @staticmethod
    def _calculate_xargus(xargus_bean: dict) -> str:
        protobuf = pad(bytes.fromhex(ProtoBuf(xargus_bean).toBuf().hex()), block_size)
        new_len = len(protobuf)
        sign_key = b"\xac\x1a\xda\xae\x95\xa7\xaf\x94\xa5\x11J\xb3\xb3\xa9}\xd8\x00P\xaa\n91L@R\x8c\xae\xc9RV\xc2\x8c"
        sm3_output = b"\xfcx\xe0\xa9ez\x0ct\x8c\xe5\x15Y\x90<\xcf\x03Q\x0eQ\xd3\xcf\xf22\xd7\x13C\xe8\x8a2\x1cS\x04"
        key = sm3_output[:32]
        key_list = []
        enc_pb = bytearray(new_len)
        for i in range(2):
            key_list.extend(list(unpack("<QQ", key[i * 16: i * 16 + 16])))
        for i in range(int(new_len / 16)):
            pt = list(unpack("<QQ", protobuf[i * 16: i * 16 + 16]))
            ct = Argus._simon.encrypt(pt, key_list)
            enc_pb[i * 16: i * 16 + 8] = ct[0].to_bytes(8, byteorder="little")
            enc_pb[i * 16 + 8: i * 16 + 16] = ct[1].to_bytes(8, byteorder="little")
        b_buffer = Argus._encrypt_enc_pb(
            (b"\xf2\xf7\xfc\xff\xf2\xf7\xfc\xff" + enc_pb), new_len + 8
        )
        b_buffer = b"\xa6n\xad\x9fw\x01\xd0\x0c\x18" + b_buffer + b"ao"
        cipher = new(md5(sign_key[:16]).digest(), MODE_CBC, md5(sign_key[16:]).digest())
        return b64encode(b"\xf2\x81" + cipher.encrypt(pad(b_buffer, block_size))).decode("utf-8")

    @staticmethod
    def _calculate_app_version(version_name: str) -> int:
        parts = version_name.split(".")
        while len(parts) < 3:
            parts.append("0")
        app_version_hash = bytes.fromhex(
            "{:x}{:x}{:x}00".format(
                int(parts[2]) * 4,
                int(parts[1]) * 16,
                int(parts[0]) * 4,
            ).zfill(8)
        )
        return int.from_bytes(app_version_hash, byteorder="big") << 1

    @staticmethod
    def encrypt(
        params: Union[str, Dict],
        data: Optional[Union[str, Dict, bytes]] = None,
        unix: Optional[int] = None,
        device_id: Optional[str] = None,
        aid: Union[str, int] = APP_DEFAULTS.aid,
        lc_id: Union[str, int] = APP_DEFAULTS.lc_id,
        sdk_ver: str = APP_DEFAULTS.sdk_ver,
        sdk_ver_code: Union[str, int] = APP_DEFAULTS.sdk_ver_code,
        version_name: str = APP_DEFAULTS.version_name,
        version_code: Union[str, int, None] = None,
    ) -> Dict[str, str]:
        aid = int(aid) if isinstance(aid, str) else aid
        lc_id = int(lc_id) if isinstance(lc_id, str) else lc_id
        sdk_ver_code = int(sdk_ver_code) if isinstance(sdk_ver_code, str) else sdk_ver_code
        if version_code is None:
            version_code = version_code_for(version_name)
        version_code = int(version_code)
        ts = unix if unix is not None else int(time())
        if isinstance(params, dict):
            params_str = urlencode(params)
        else:
            params_str = str(params)
        params_dict = parse_qs(params_str)
        channel = params_dict.get("channel", [Argus.DEFAULT_CHANNEL])[0]
        device_id = params_dict.get("device_id", [uuid4().hex[:16]])[0] if not device_id else device_id
        device_type = params_dict.get("device_type", [Argus.DEFAULT_DEVICE_TYPE])[0]
        os_version = params_dict.get("os_version", [Argus.DEFAULT_OS_VERSION])[0]
        version_name = params_dict.get("version_name", [version_name])[0]
        stub = None
        if data is not None:
            stub = generate_stub(data)
        xargus_bean = {
            1: 0x20200929 << 1,
            2: 2,
            3: randint(0, 0x7FFFFFFF),
            4: str(aid),
            5: device_id,
            6: str(lc_id),
            7: sdk_ver,
            8: sdk_ver,
            9: sdk_ver_code,
            10: bytes(8),
            11: "android",
            12: ts << 1,
            13: Argus._get_bodyhash(stub),
            14: Argus._get_queryhash(params_str),
            15: {1: 85, 2: 85, 3: 85, 5: 85, 6: 170, 7: (ts << 1) - 310},
            16: device_id,
            20: "none",
            21: 738,
            23: {
                1: device_type,
                2: os_version,
                3: channel,
                4: Argus._calculate_app_version(version_name),
            },
            25: 2,
        }
        return {"x-argus": Argus._calculate_xargus(xargus_bean)}
