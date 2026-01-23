# -*- coding: utf-8 -*-
"""
font_subset_batch.py
批量裁剪字体，确保：
- 半角空格和全角空格都能显示
- GB2312 全字都包含
"""

import os
import subprocess
from pathlib import Path

# 字符集文件
CHARS_FILE = r"D:\tools\font\chars.txt"

# 要裁剪的字体列表
INPUT_FONTS = [
    r"D:\apk\font\OPPOSanSB.ttf",
    r"D:\apk\font\OPPOSanSR.ttf",  # 可以继续添加更多字体
]

# 半角可显示空格 Unicode
VISIBLE_HALF_SPACE = "\u00A0"  # non-breaking space
FULL_WIDTH_SPACE = "\u3000"     # 全角空格

def read_chars(chars_file):
    """
    读取 chars.txt，并做字符处理：
    - 去掉换行符
    - 将半角空格替换为可显示空格（U+00A0）
    - 保留全角空格
    """
    with open(chars_file, "r", encoding="utf-8") as f:
        chars = f.read()
    
    # 去掉换行符
    chars = chars.replace("\n", "").replace("\r", "")
    
    # 替换半角空格为可显示空格
    chars = chars.replace(" ", VISIBLE_HALF_SPACE)
    
    # 确保全角空格在字符集里
    if FULL_WIDTH_SPACE not in chars:
        chars += FULL_WIDTH_SPACE
    
    return chars

def subset_font(input_font, chars):
    """
    调用 pyftsubset 裁剪字体
    """
    input_path = Path(input_font)
    output_dir = input_path.parent / "cut"
    output_dir.mkdir(exist_ok=True)

    output_font = output_dir / input_path.name

    cmd = [
        "pyftsubset",
        str(input_path),
        f"--output-file={output_font}",
        f"--text={chars}",
        "--glyph-names",
        "--symbol-cmap",
        "--legacy-cmap",
        "--notdef-glyph",
        "--notdef-outline",
        "--recommended-glyphs",
    ]

    print(f"裁剪字体: {input_path.name} -> {output_font}")
    subprocess.run(cmd, check=True)
    print(f"✅ 完成: {output_font}")

if __name__ == "__main__":
    if not os.path.exists(CHARS_FILE):
        print(f"❌ chars.txt 文件不存在: {CHARS_FILE}")
        exit(1)

    chars = read_chars(CHARS_FILE)

    for font_path in INPUT_FONTS:
        if not os.path.exists(font_path):
            print(f"⚠️ 字体不存在: {font_path}, 跳过")
            continue
        subset_font(font_path, chars)
