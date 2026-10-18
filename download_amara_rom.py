import os
import sys
import time
import re
import urllib.request
import http.cookiejar
import hashlib

sys.stdout.reconfigure(encoding='utf-8')

FILE_ID = "1y0lK3HPsdH2ASfmw-LDe7z6lONWi5mp7"
DEST_PATH = r"c:\Users\ACER\Downloads\note8_amara_oneui7\exynos8895-15.0.0_v1.0.2a-20250131.zip"

print(f"[*] Preparing download for Google Drive File ID: {FILE_ID}")
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

initial_url = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&authuser=0"
req = urllib.request.Request(initial_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
resp = opener.open(req)

headers = resp.info()
content_type = headers.get_content_type()
print(f"[*] Initial response Content-Type: {content_type}")

if content_type == "text/html":
    body = resp.read().decode('utf-8', 'ignore')
    match_uuid = re.search(r'name="uuid"\s+value="([^"]+)"', body)
    uuid_val = match_uuid.group(1) if match_uuid else ""
    print(f"[*] Extracted confirmation token uuid: {uuid_val}")
    
    download_url = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&authuser=0&confirm=t&uuid={uuid_val}"
    req2 = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    resp = opener.open(req2)
    headers = resp.info()
    content_type = headers.get_content_type()
    print(f"[*] Secondary response Content-Type: {content_type}")

total_length = headers.get('Content-Length')
if total_length:
    total_bytes = int(total_length)
    print(f"[*] Total file size: {total_bytes / (1024*1024):.2f} MB ({total_bytes} bytes)")
else:
    total_bytes = None
    print("[*] Total file size: Unknown (chunked stream)")

print(f"[*] Downloading to: {DEST_PATH}")
chunk_size = 1024 * 1024 # 1 MB
downloaded = 0
start_time = time.time()
last_report = start_time

sha256 = hashlib.sha256()

with open(DEST_PATH, "wb") as f:
    while True:
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        f.write(chunk)
        sha256.update(chunk)
        downloaded += len(chunk)
        
        now = time.time()
        if now - last_report >= 5: # report every 5 seconds
            elapsed = now - start_time
            speed = downloaded / (1024 * 1024 * elapsed) if elapsed > 0 else 0
            if total_bytes:
                pct = (downloaded / total_bytes) * 100
                print(f"[>] Progress: {pct:.1f}% ({downloaded / (1024*1024):.1f}/{total_bytes / (1024*1024):.1f} MB) @ {speed:.2f} MB/s")
            else:
                print(f"[>] Downloaded: {downloaded / (1024*1024):.1f} MB @ {speed:.2f} MB/s")
            last_report = now

total_time = time.time() - start_time
avg_speed = downloaded / (1024 * 1024 * total_time) if total_time > 0 else 0
print(f"[+] Download completed successfully in {total_time:.1f}s ({avg_speed:.2f} MB/s)!")
print(f"[+] File size: {os.path.getsize(DEST_PATH)} bytes")
print(f"[+] SHA256: {sha256.hexdigest()}")
