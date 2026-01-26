# -*- coding: utf-8 -*-
"""
font_subset_batch.py
批量裁剪字体
"""

import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 字符集文件
CHARS_FILE = BASE_DIR / "chars.txt"

# 要裁剪的字体列表
INPUT_FONTS = [
    BASE_DIR / "OPPOSanSB.ttf",
    BASE_DIR / "OPPOSanSR.ttf",
]


def read_chars(chars_file):
    """
    读取 chars.txt，并做最小、正确的工程处理：
    - 去掉换行符
    """
    with open(chars_file, "r", encoding="utf-8") as f:
        chars = f.read()

    # 去掉换行符（pyftsubset --text 不需要）
    chars = chars.replace("\n", "").replace("\r", "")

    return chars


def subset_font(input_font, chars):
    """
    调用 pyftsubset 裁剪字体
    """
    input_path = Path(input_font)
    output_dir = input_path.parent / "output"
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

    print(f"✂️ 裁剪字体: {input_path.name}")
    subprocess.run(cmd, check=True)
    print(f"✅ 输出完成: {output_font}")


if __name__ == "__main__":
    if not os.path.exists(CHARS_FILE):
        print(f"❌ chars.txt 不存在: {CHARS_FILE}")
        exit(1)

    chars = read_chars(CHARS_FILE)

    print(f"📦 字符总数: {len(chars)}")

    for font_path in INPUT_FONTS:
        if not os.path.exists(font_path):
            print(f"⚠️ 字体不存在，跳过: {font_path}")
            continue
        subset_font(font_path, chars)
