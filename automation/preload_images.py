#!/usr/bin/env python3
"""Pre-generate high-quality cat podcast background images for caching."""
import os
import sys
import time
import hashlib
import requests

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_images")

PROMPTS = [
    "two cute cartoon cats sitting at podcast microphones in a cozy warm studio, orange tabby and black cat, wooden desk, soft warm lighting, plant pots, bookshelves, professional podcast setup, no text no words no letters, high quality digital art",
    "two cartoon cats recording a podcast, one orange tabby one black, sitting on cozy armchairs with microphones, warm ambient lighting, studio with acoustic panels and plants, no text no words, detailed illustration",
    "cartoon cats podcast studio scene, two cats at a desk with professional microphones, warm cozy atmosphere, bookshelves in background, soft golden lighting, no text no letters no signage, digital painting",
    "two animated cats hosting a podcast, orange tabby and black cat, sitting across from each other with microphones, warm studio with wooden accents and green plants, soft bokeh lighting, no text, high quality render",
    "cute podcast studio with two cartoon cats, one orange one black, talking into microphones, cozy interior with warm lamps, bookshelves, plants on desk, no text no words, vibrant digital illustration",
    "two cartoon cats in a professional podcast studio, orange tabby cat and black cat, microphones on adjustable arms, warm wooden desk, soft studio lighting, acoustic foam panels, plants, no text, detailed art",
    "cartoon illustration of two cats recording podcast episode, cozy studio setting, orange tabby and black cat at microphones, warm lighting, bookshelves and plants in background, no text no words, quality art",
    "two cute cats podcasting in warm studio, orange tabby and black cat sitting at desk with microphones, cozy armchairs, ambient warm lighting, plants and books, no text no letters, beautiful digital art",
]

def generate_images(count=8):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    existing = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg') and not f.startswith('episode')]
    if len(existing) >= count:
        print(f"Already have {len(existing)} cached images, skipping.")
        return

    for i, prompt in enumerate(PROMPTS[:count]):
        print(f"  Generating image {i+1}/{count}...")
        try:
            url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1280&height=720&nologo=true&model=flux&seed={i*42}"
            resp = requests.get(url, timeout=60, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                img_path = os.path.join(IMAGES_DIR, f"cat_podcast_{i+1:02d}_{hashlib.md5(resp.content).hexdigest()[:6]}.jpg")
                with open(img_path, 'wb') as f:
                    f.write(resp.content)
                print(f"    Saved: {os.path.basename(img_path)} ({len(resp.content)} bytes)")
            else:
                print(f"    Failed: status={resp.status_code}, size={len(resp.content)}")
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(2)  # rate limit

    final = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg') and not f.startswith('episode')]
    print(f"\nTotal cached images: {len(final)}")

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    generate_images(count)
