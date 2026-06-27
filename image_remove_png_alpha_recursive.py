import os
import sys
from PIL import Image

def process_png(input_root):
    input_root = os.path.abspath(input_root)
    output_root = os.path.join(input_root, "out")

    for root, dirs, files in os.walk(input_root):
        # 避免处理 out 目录本身
        if root.startswith(output_root):
            continue

        for file in files:
            if file.lower().endswith(".png"):
                input_path = os.path.join(root, file)

                # 计算相对路径
                relative_path = os.path.relpath(root, input_root)
                output_dir = os.path.join(output_root, relative_path)
                os.makedirs(output_dir, exist_ok=True)

                output_path = os.path.join(output_dir, file)

                try:
                    img = Image.open(input_path)

                    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
                        background = Image.new("RGB", img.size, (0, 0, 0))
                        alpha = img.split()[-1]
                        background.paste(img, mask=alpha)
                        background.save(output_path)
                        print(f"[OK] Alpha removed: {input_path}")
                    else:
                        img.convert("RGB").save(output_path)
                        print(f"[OK] No alpha: {input_path}")

                except Exception as e:
                    print(f"[ERR] {input_path} -> {e}")

    print("\nDone.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python remove_alpha_recursive.py <input_folder>")
        sys.exit(1)

    input_folder = sys.argv[1]

    if not os.path.isdir(input_folder):
        print("Error: Input path is not a directory")
        sys.exit(1)

    process_png(input_folder)
