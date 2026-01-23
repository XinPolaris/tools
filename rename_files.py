import os
import sys

# ========== 默认配置 ==========
DEFAULT_PREFIX = "test"
START_INDEX = 1
DIGITS = 1
# ==============================

def main():
    if len(sys.argv) < 2:
        print("❌ 用法错误")
        print("用法: python rename_files.py <folder_path> [prefix]")
        return

    folder = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_PREFIX

    if not os.path.isdir(folder):
        print(f"❌ 不是有效的文件夹: {folder}")
        return

    files = [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]

    if not files:
        print("⚠ 文件夹里没有文件")
        return

    files.sort()

    print(f"📂 处理文件夹: {folder}")
    print(f"🏷 使用前缀: {prefix}")
    print(f"📄 找到 {len(files)} 个文件\n")

    for i, old_name in enumerate(files, START_INDEX):
        _, ext = os.path.splitext(old_name)
        new_name = f"{prefix}{str(i).zfill(DIGITS)}{ext}"

        old_path = os.path.join(folder, old_name)
        new_path = os.path.join(folder, new_name)

        print(f"{old_name}  ->  {new_name}")
        os.rename(old_path, new_path)

    print("\n✅ 批量重命名完成")

if __name__ == "__main__":
    main()
