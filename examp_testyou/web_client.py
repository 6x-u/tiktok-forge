"""End-to-end web call: signed request, retry on a rejected signature."""

from tiktokforge import WebClient

with WebClient(retries=2) as client:
    print("cookies after bootstrap:", client.session.cookies.get_dict().keys())
    resp = client.get("/api/challenge/detail/", params={"challengeName": "fyp"})
    print("status:", resp.status_code, "bytes:", len(resp.content))
    data = resp.json()
    info = data.get("challengeInfo", {}).get("challenge", {})
    print("challenge id:", info.get("id"))
    print("video count:", info.get("stats", {}).get("videoCount"))

    # a POST is signed over the body too (body enters the signature payload)
    post = client.post("/api/comment/list/", params={"aweme_id": "8032982342441467163", "count": 5})
    print("post status:", post.status_code, "bytes:", len(post.content))
