#!/usr/bin/env python3
"""
Generate 25 AI images of a modern Logitech mouse from multiple angles
for photogrammetry pipeline testing using OpenAI's DALL-E API.
"""

import os
import requests
import base64
import json
from pathlib import Path
import time

# Configuration
output_dir = Path("/home/harpreet/Documents/3d_scanner/assets/mouse_ai_images")
output_dir.mkdir(exist_ok=True)

num_images = 25
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set")
    print("Please set it with: export OPENAI_API_KEY='your-api-key'")
    exit(1)

# Generate prompts for different angles
def generate_prompts():
    """Generate prompts for 25 images from different angles."""
    prompts = []
    
    # Base prompt for modern Logitech mouse
    base_prompt = "A modern Logitech computer mouse, professional product photography, high resolution, detailed texture, clean white background, studio lighting, 4K quality"
    
    # Different angles
    angles = [
        "front view",
        "top-down view",
        "side view left",
        "side view right",
        "back view",
        "angled view from top left",
        "angled view from top right",
        "angled view from bottom left",
        "angled view from bottom right",
        "close-up of scroll wheel",
        "close-up of left and right buttons",
        "close-up of DPI indicator light",
        "side profile view",
        "three-quarter view",
        "overhead view",
        "bottom view showing USB cable",
        "angled front view",
        "angled back view",
        "close-up of mouse feet",
        "wide shot showing entire mouse",
        "detail shot of mouse texture",
        "angled shot from above",
        "angled shot from below",
        "front-left diagonal view",
        "front-right diagonal view"
    ]
    
    for i, angle in enumerate(angles):
        prompt = f"{base_prompt}, {angle}"
        prompts.append(prompt)
    
    return prompts

def generate_image(prompt, index):
    """Generate a single image using DALL-E API."""
    url = "https://api.openai.com/v1/images/generations"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "hd",
        "response_format": "b64_json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        image_data = result["data"][0]["b64_json"]
        
        # Decode and save image
        image_bytes = base64.b64decode(image_data)
        output_path = output_dir / f"mouse_ai_{index+1:02d}.png"
        
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        
        print(f"✅ Generated image {index+1}/{num_images}: {prompt[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error generating image {index+1}: {e}")
        return False

def main():
    """Main function to generate all images."""
    print(f"Generating {num_images} AI images of modern Logitech mouse...")
    
    prompts = generate_prompts()
    
    success_count = 0
    for i, prompt in enumerate(prompts):
        print(f"\nGenerating image {i+1}/{num_images}...")
        if generate_image(prompt, i):
            success_count += 1
        
        # Rate limiting - wait between requests
        if i < len(prompts) - 1:
            time.sleep(2)
    
    print(f"\n✅ Generated {success_count}/{num_images} images in {output_dir}")

if __name__ == "__main__":
    main()
