"""Device-register flow: gzip + TTEncrypt body, signed with Argus/Gorgon/Ladon."""

import requests

from tiktokforge import APP_DEFAULTS, TikTokSigner

device_info = {
    "magic_tag": "ss_app_log",
    "header": {
        "display_name": "TikTok",
        "aid": 1233,
        "channel": "googleplay",
        "package": "com.zhiliaoapp.musically",
        "version_name": APP_DEFAULTS.version_name,
        "version_code": APP_DEFAULTS.version_code,
        "os": "Android",
        "os_version": APP_DEFAULTS.device.os_version,
        "os_api": APP_DEFAULTS.device.os_api,
        "device_model": APP_DEFAULTS.device.device_type,
        "device_brand": APP_DEFAULTS.device.device_brand,
        "cpu_abi": APP_DEFAULTS.device.cpu_abi,
        "language": APP_DEFAULTS.device.language,
        "timezone": APP_DEFAULTS.device.timezone,
    },
    "_gen_time": 1792998000000,
}

body = TikTokSigner.encrypt(device_info)
print(f"payload: {len(body)} bytes, magic {body[:4].hex()}")

params = (
    f"aid=1233&app_name=musical_ly&device_platform=android"
    f"&version_code={APP_DEFAULTS.version_code}&version_name={APP_DEFAULTS.version_name}"
    f"&device_id=7171234567890123456&os_version={APP_DEFAULTS.device.os_version}"
)
headers = {
    "User-Agent": APP_DEFAULTS.user_agent(),
    "Content-Type": "application/octet-stream",
}
headers.update(TikTokSigner.generate_headers(params=params, data=body))

url = "https://log.tiktokv.com/service/2/device_register/?" + params
print("url:", url)
print("headers:", ", ".join(sorted(headers)))

# uncomment to send for real
# resp = requests.post(url, headers=headers, data=body, timeout=30)
# print(resp.status_code, resp.text[:400])
