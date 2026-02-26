import sys
from pathlib import Path

import cv2

from southview.ocr.preprocess import preprocess_image

def main():
    if len(sys.argv) != 2:
        print(r'Usage: python tools\run_preprocess_png.py "C:\Users\level\Desktop\South_View_OCR\southview-OCR\example_cards\AARON_BENJAMIN(NEW).png"')
        raise SystemExit(2)

    img_path = Path(sys.argv[1])
    if not img_path.exists():
        raise FileNotFoundError(img_path)

    # Write debug images here
    debug_dir = Path("debug/preprocess")
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Your preprocess_image reads from a path and returns a processed image (2D array)
    out = preprocess_image(img_path, debug_dir=str(debug_dir))

    # Save a final output explicitly
    cv2.imwrite(str(debug_dir / "final.png"), out)

    print(f"Wrote: {debug_dir}\\*.png")

if __name__ == "__main__":
    main()