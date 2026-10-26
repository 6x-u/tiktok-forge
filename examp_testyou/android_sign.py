

from tiktokforge import APP_DEFAULTS, TikTokSigner
from tiktokforge.algorithms import Argus, Gorgon, Ladon
from tiktokforge.config import DeviceProfile, AppDefaults

print(f"app build: {APP_DEFAULTS.version_name} ({APP_DEFAULTS.version_code})")
print(f"ua: {APP_DEFAULTS.user_agent()}\n")

params = (
    "aid=1233&app_name=musical_ly&device_platform=android"
    "&os_version=14&device_type=Pixel%207&channel=googleplay"
    "&device_id=7171234567890123456&version_name=47.5.3"
)

print("=== TikTokSigner.generate_headers() ===")
headers = TikTokSigner.generate_headers(params=params, data="username=demo&mix_mode=1")
for key, value in headers.items():
    shown = value[:64] + "..." if len(value) > 64 else value
    print(f"  {key}: {shown}")

print("\n=== individual algorithms ===")
print("  x-ladon: ", Ladon.encrypt(aid=1233, lc_id=2142840551)["x-ladon"][:40], "...")
gorgon = Gorgon.encrypt(params=params)
print("  x-gorgon:", gorgon["x-gorgon"])
print("  x-khronos:", gorgon["x-khronos"])
print("  x-argus: ", Argus.encrypt(params=params)["x-argus"][:40], "...")

print("\n=== pinned device profile ===")
device = DeviceProfile(
    device_id="7171234567890123456",
    install_id="7171234567890123457",
    device_type="SM-S928B",
    device_brand="samsung",
    os_version="15",
    os_api=35,
)
profile = AppDefaults(device=device)
print(f"  ua: {profile.user_agent()}")
pinned = TikTokSigner.generate_headers(params=params, profile=profile)
print(f"  trace: {pinned['x-tt-trace-id']}")

print("\n=== ttencrypt device register payload ===")
blob = TikTokSigner.encrypt({"device_id": device.device_id, "os": "android", "aid": 1233})
print(f"  cipher: {len(blob)} bytes, magic {blob[:4].hex()}")
print(f"  decrypt: {TikTokSigner.decrypt(blob)}")
