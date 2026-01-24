# generate_chars_from_gb2312.py
# 从 GB2312.TXT 生成 chars.txt
# 支持半角空格 + 全角空格 + ASCII 数字/字母/常用标点 + GB2312 全量汉字

GB2312_MAPPING_FILE = r"C:\tools\font\mappings\GB2312.TXT"
OUTPUT_FILE = "chars.txt"

def main():
    chars = []

    # 1. 半角空格
    chars.append(" ")  # ASCII 0x20

    # 2. ASCII 可见字符（包含数字、英文、标点）
    for code in range(0x21, 0x7F):  # 0x21~0x7E，避开重复的半角空格
        chars.append(chr(code))

    # 3. 全角空格
    chars.append("\u3000")  # 全角空格

    # 4. 读取 GB2312 映射文件
    with open(GB2312_MAPPING_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            unicode_hex = parts[1]
            try:
                codepoint = int(unicode_hex, 16)
                chars.append(chr(codepoint))
            except ValueError:
                continue

    # 5. 去重（保持顺序）
    chars = list(dict.fromkeys(chars))

    # 6. 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("".join(chars))

    print(f"✅ chars.txt 生成完成")
    print(f"📦 字符总数: {len(chars)}（GB2312 全量 + ASCII + 半/全角空格 + 标点）")


if __name__ == "__main__":
    main()
