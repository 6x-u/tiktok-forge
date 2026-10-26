"""Web signatures — X-Bogus comes from TikTok's own bundle via the node bridge."""

from tiktokforge import (
    WEB_USER_AGENT,
    generate_ms_token,
    generate_verify_fp,
    generate_web_headers,
    generate_web_id,
    generate_x_bogus,
    sign_web,
    with_signature,
)

query = "aid=1988&app_name=tiktok_web&device_platform=web_pc&count=20&cursor=0"

print("=== tokens ===")
print(f"  msToken:  {generate_ms_token()}  (107 chars)")
print(f"  verifyFp: {generate_verify_fp()}")
print(f"  webId:    {generate_web_id()}")

print("\n=== X-Bogus (live SDK) ===")
print(f"  {sign_web(query, user_agent=WEB_USER_AGENT)}")
print(f"  again: {generate_x_bogus(query)}")
print(f"  url:   {with_signature('https://www.tiktok.com/api/challenge/detail/?' + query)}")

print("\n=== full header set ===")
headers = generate_web_headers("https://www.tiktok.com/api/challenge/detail/?" + query)
for key, value in headers.items():
    shown = value[:70] + "..." if len(value) > 70 else value
    print(f"  {key}: {shown}")
