import subprocess, re

xml = subprocess.check_output(['adb', 'shell', 'cat', '/sdcard/window_dump.xml']).decode('utf-8', errors='ignore')
matches = re.findall(r'text="([^"]+)"[^>]+bounds="(\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\])"', xml)
for text, bounds in matches:
    print(f"{text} -> {bounds}")
