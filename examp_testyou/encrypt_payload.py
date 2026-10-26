"""TTEncrypt payload round-trip plus protobuf encode/decode."""

import json

from tiktokforge import APP_DEFAULTS, TikTokSigner, decode, encode

device_info = {
    "magic_tag": "ss_app_log",
    "header": {
        "aid": 1233,
        "os": "Android",
        "os_version": APP_DEFAULTS.device.os_version,
        "device_model": APP_DEFAULTS.device.device_type,
        "version_name": APP_DEFAULTS.version_name,
        "version_code": APP_DEFAULTS.version_code,
    },
}

payload = json.dumps(device_info, separators=(",", ":"))
print("=== TTEncrypt (device register payload) ===")
print(f"  plain:     {len(payload)} chars")
blob = TikTokSigner.encrypt(payload)
print(f"  cipher:    {len(blob)} bytes, magic {blob[:4].hex()}")
print(f"  roundtrip: {TikTokSigner.decrypt(blob) == payload}")

print("\n=== protobuf ===")
data = {1: "hello_world", 2: 42, 3: 1706789012}
encoded = encode(data)
print(f"  encoded: {encoded.hex()}")
decoded = decode(encoded)
print(f"  decoded: {decoded}")
assert decoded[1] == "hello_world" and decoded[2] == 42

nested = {1: "outer", 2: {1: "inner", 2: 7}}
print(f"  nested:  {decode(encode(nested))}")
