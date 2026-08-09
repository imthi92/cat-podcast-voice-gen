#!/usr/bin/env python3
"""
Resize images for YouTube channel assets
"""

import os
import sys
from PIL import Image

# YouTube dimensions
DIMENSIONS = {
    "profile_picture": (800, 800),
    "banner": (2560, 1440),
    "thumbnail": (1280, 720),
    "simba": (800, 800),
    "meow": (800, 800),
}

def resize_image(input_path, output_path, target_size, crop_center=True):
    """Resize image to target size, cropping from center if needed."""
    img = Image.open(input_path)

    # Calculate crop to match aspect ratio
    target_ratio = target_size[0] / target_size[1]
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider, crop sides
        new_height = img.height
        new_width = int(new_height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, new_height))
    else:
        # Image is taller, crop top/bottom
        new_width = img.width
        new_height = int(new_width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, new_width, top + new_height))

    # Resize to target
    img = img.resize(target_size, Image.Resampling.LANCZOS)

    # Save
    img.save(output_path, "PNG", quality=95)
    print(f"  Created: {output_path} ({target_size[0]}x{target_size[1]})")


def main():
    print("=" * 50)
    print("YouTube Channel Assets - Image Resizer")
    print("=" * 50)

    # Check for images
    input_dir = "./downloaded_images"
    output_dir = "./youtube_assets"

    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"\nCreated folder: {input_dir}")
        print("Put your downloaded images in this folder and run again.")
        return

    # List images
    images = [f for f in os.listdir(input_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not images:
        print(f"\nNo images found in {input_dir}")
        print("Put your downloaded images in this folder:")
        print(f"  {os.path.abspath(input_dir)}")
        return

    print(f"\nFound {len(images)} images:")
    for i, img in enumerate(images, 1):
        print(f"  {i}. {img}")

    # Ask user to assign images
    print("\nAssign images to YouTube assets:")
    print("  1 = Profile Picture (800x800)")
    print("  2 = Banner (2560x1440)")
    print("  3 = Thumbnail Template (1280x720)")
    print("  4 = Simba Character (800x800)")
    print("  5 = Meow Character (800x800)")

    assignments = {}
    for asset_name, size in DIMENSIONS.items():
        while True:
            choice = input(f"\n{asset_name.replace('_', ' ').title()} - Enter image number (or 'skip'): ").strip()
            if choice.lower() == 'skip':
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(images):
                    assignments[asset_name] = images[idx]
                    break
                else:
                    print("Invalid number, try again")
            except ValueError:
                print("Enter a number or 'skip'")

    if not assignments:
        print("\nNo images assigned. Exiting.")
        return

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Resize images
    print("\nResizing images...")
    for asset_name, filename in assignments.items():
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, f"{asset_name}.png")
        target_size = DIMENSIONS[asset_name]
        resize_image(input_path, output_path, target_size)

    # Create thumbnail with text (optional)
    print("\n" + "=" * 50)
    print("DONE!")
    print("=" * 50)
    print(f"\nYouTube assets saved in: {output_dir}")
    print("\nFiles created:")
    for f in os.listdir(output_dir):
        print(f"  - {f}")

    print("\nUpload to YouTube:")
    print("  1. Profile Picture: YouTube Studio -> Customization -> Branding")
    print("  2. Banner: YouTube Studio -> Customization -> Branding")
    print("  3. Thumbnails: Upload with each video")


if __name__ == "__main__":
    main()