import urllib.request
import json
import http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

# 1. Login to get session
login_payload = json.dumps({"email": "ceo@audible.ai", "password": "Audible2026!"}).encode()
req_login = urllib.request.Request(
    "http://localhost:3010/api/v1/auth/login",
    data=login_payload,
    headers={"Content-Type": "application/json"}
)
with opener.open(req_login) as resp:
    token_data = json.loads(resp.read().decode())
    token = token_data["token"]
    print("1. Login OK, token length:", len(token))

# Set session cookie on web app
req_session = urllib.request.Request(
    "http://localhost:3010/api/auth/session",
    data=json.dumps({"token": token, "user": token_data["user"]}).encode(),
    headers={"Content-Type": "application/json"}
)
with opener.open(req_session) as resp:
    print("2. Session cookie set:", resp.status)

# 2. Fetch HomePage /
req_home = urllib.request.Request("http://localhost:3010/")
with opener.open(req_home) as resp:
    print("3. Final HomePage URL:", resp.geturl())
    html = resp.read().decode("utf-8")
    print("Contains 'Phone calling requires a telephony connection':", "Phone calling requires a telephony connection" in html)
    print("Contains 'Talk to Bridget in Browser':", "Talk to Bridget in Browser" in html)
    print("Contains 'Guided Telephony Setup':", "Guided Telephony Setup" in html)
