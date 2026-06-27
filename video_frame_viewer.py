from PIL import Image
import os
import sys

def raw_to_png(file_path, width, height, bpp=32, out_path="frame.png"):
    pixel_size = bpp // 8
    mode = "RGBA" if bpp == 32 else "RGB"

    if not os.path.exists(file_path):
        print(f"❌ RAW file not found: {file_path}")
        return

    actual_size = os.path.getsize(file_path)
    expected_size = width * height * pixel_size
    print(f"RAW file size: {actual_size}, expected: {expected_size}")

    if actual_size < expected_size:
        print("⚠️ WARNING: RAW data too small, image may be incomplete")

    with open(file_path, "rb") as f:
        data = f.read(expected_size if actual_size >= expected_size else actual_size)

    try:
        img = Image.frombytes(mode, (width, height), data)
    except Exception as e:
        print("❌ Error creating image:", e)
        return

    # BGRA -> RGBA
    if bpp == 32:
        r, g, b, a = img.split()
        img = Image.merge("RGBA", (b, g, r, a))

    img.save(out_path)
    print(f"✅ Saved PNG: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python frame_viewer.py <raw_file> <width> <height> [bpp] [out.png]")
        sys.exit(1)

    raw_file = sys.argv[1]
    width = int(sys.argv[2])
    height = int(sys.argv[3])
    bpp = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    out_png = sys.argv[5] if len(sys.argv) > 5 else "frame.png"

    raw_to_png(raw_file, width, height, bpp, out_png)
