import os
import hashlib
import zipfile

d = r"c:\Users\ACER\Downloads\note8_amara_oneui7"
files = sorted(os.listdir(d))

print("=== FILE INTEGRITY CHECK ===")
for f in files:
    full_path = os.path.join(d, f)
    size = os.path.getsize(full_path)
    h = hashlib.sha256()
    with open(full_path, "rb") as fp:
        while chunk := fp.read(1024 * 1024 * 8):
            h.update(chunk)
    print(f"File: {f}")
    print(f"  Size: {size:,} bytes ({size / (1024*1024):.2f} MB)")
    print(f"  SHA256: {h.hexdigest().upper()}")
    if f.endswith(".zip"):
        try:
            with zipfile.ZipFile(full_path) as z:
                ret = z.testzip()
                if ret is None:
                    print("  Zip Test: PASSED (Archive clean, zero corruption)")
                else:
                    print(f"  Zip Test: CORRUPTED at {ret}")
        except Exception as e:
            print(f"  Zip Test: FAILED ({e})")
    print()
