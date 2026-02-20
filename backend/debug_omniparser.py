import requests
import base64
import os
import io

# Path to an existing screenshot artifact
img_path = r'C:\Users\H\.gemini\antigravity\brain\f8953c63-0ea1-40a5-adf2-4ded6c1d1fa7\media__1771503080361.png'
url = 'http://localhost:7861/parse'

try:
    if not os.path.exists(img_path):
        print(f"Error: Path {img_path} does not exist.")
        exit(1)

    with open(img_path, 'rb') as f:
        img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    
    print(f"Sending request to {url} with image size {len(img_b64)} bytes...")
    
    # Simple JSON payload as expected by OmniParser
    resp = requests.post(url, json={'base64_image': img_b64}, timeout=60)
    
    print(f"Status Code: {resp.status_code}")
    print(f"Response (truncated): {resp.text[:5000]}")

except Exception as e:
    print(f"FAILED: {e}")
