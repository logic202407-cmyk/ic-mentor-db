"""Process and convert user uploaded GPT Image 2 renders to optimized WebP and PNG."""

import os
from pathlib import Path
from PIL import Image

USER_UPLOADED_DIR = Path(r"C:\Users\WPY11\.gemini\antigravity\brain\d0af649c-af1a-46db-86a3-1e97cfd70138\.user_uploaded")
OUTPUT_DIR = Path(r"D:\ic-mentor-db\workbench\web\assets\visuals")

MAPPING = {
    "hero-academic": "media_1792900650725_3d0401de.png",
    "source-academic": "media_1792900650728_37e48182.png",
    "search-empty": "media_1792900650746_614349e4.png",
    "discipline-explore": "media_1792900650693_0ebf9c3b.png",
    "about-academic": "media_1792900650710_17444c7c.png",
    "records-empty": "media_1792901784317_73388470.png",
}

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Processing 6 images from user_uploaded to visuals...")
    
    for name, filename in MAPPING.items():
        src_path = USER_UPLOADED_DIR / filename
        if not src_path.exists():
            print(f"Error: {src_path} does not exist!")
            continue
        
        with Image.open(src_path) as img:
            print(f"Loaded {name}: {img.size}, mode={img.mode}")
            
            # Ensure RGBA mode for transparency
            if img.mode != "RGBA":
                img = img.convert("RGBA")
                
            # 1. Save standard PNG fallback
            png_dest = OUTPUT_DIR / f"{name}.png"
            img.save(png_dest, format="PNG", optimize=True)
            png_kb = png_dest.stat().st_size / 1024
            
            # 2. Save high-efficiency WebP
            webp_dest = OUTPUT_DIR / f"{name}.webp"
            img.save(webp_dest, format="WEBP", quality=90, method=6)
            webp_kb = webp_dest.stat().st_size / 1024
            
            print(f" -> Saved {png_dest.name} ({png_kb:.1f} KB) & {webp_dest.name} ({webp_kb:.1f} KB)")
            
            # Special: mobile version for hero
            if name == "hero-academic":
                mobile_w = 640
                mobile_h = int(img.height * (mobile_w / img.width))
                mobile_img = img.resize((mobile_w, mobile_h), Image.Resampling.LANCZOS)
                mobile_dest = OUTPUT_DIR / "hero-academic-mobile.webp"
                mobile_img.save(mobile_dest, format="WEBP", quality=88, method=6)
                print(f" -> Saved mobile hero: {mobile_dest.name} ({mobile_dest.stat().st_size/1024:.1f} KB)")

if __name__ == "__main__":
    main()
