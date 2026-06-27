from PIL import Image
import os
import sys

if len(sys.argv) < 2:
    print("用法: python jpg_to_png.py <folder>")
    sys.exit(1)

folder = sys.argv[1]

if not os.path.isdir(folder):
    print("不是有效文件夹:", folder)
    sys.exit(1)

for file in os.listdir(folder):
    if file.lower().endswith(".jpg"):
        jpg_path = os.path.join(folder, file)
        png_path = os.path.join(folder, file[:-4] + ".png")

        try:
            img = Image.open(jpg_path)
            img.save(png_path, "PNG")

            os.remove(jpg_path)  # 删除原jpg

            print(f"{file} -> {file[:-4]}.png  (已删除原图)")
        except Exception as e:
            print(f"转换失败: {file}  错误: {e}")

print("转换完成")
