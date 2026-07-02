# -*- coding: utf-8 -*-
"""
font_subset_batch.py
批量裁剪字体
"""

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
CHARS_DIR = INPUT_DIR / "chars"
OUTPUT_DIR = BASE_DIR / "output"

# 参与裁剪的字符集文件；允许内容重复，合并时会自动去重。
CHARS_FILES = [
    CHARS_DIR / "chars.txt",
    CHARS_DIR / "recipe_chars.txt",
    CHARS_DIR / "extra_chars.txt",
]
MERGED_CHARS_FILE = CHARS_DIR / "subset_chars.txt"

# 要裁剪的字体列表
INPUT_FONTS = [
    INPUT_DIR / "SourceHanSansSC-Bold.otf",
    INPUT_DIR / "SourceHanSansSC-Regular.otf",
]


def merge_chars(chars_files):
    """合并多个字符集，移除换行并按首次出现顺序去重。"""
    chars = "".join(path.read_text(encoding="utf-8") for path in chars_files)
    chars = chars.replace("\n", "").replace("\r", "")
    return "".join(dict.fromkeys(chars))


def subset_font(input_font, chars_file):
    """
    调用 pyftsubset 裁剪字体
    """
    input_path = Path(input_font)
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_font = OUTPUT_DIR / f"{input_path.stem}.ttf"

    cmd = [
        "pyftsubset",
        str(input_path),
        f"--output-file={output_font}",
        f"--text-file={chars_file}",
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
    missing_chars_files = [path for path in CHARS_FILES if not path.is_file()]
    if missing_chars_files:
        for path in missing_chars_files:
            print(f"❌ 字符集文件不存在: {path}")
        exit(1)

    chars = merge_chars(CHARS_FILES)
    MERGED_CHARS_FILE.write_text(chars, encoding="utf-8")

    print(f"📦 字符总数: {len(chars)}")
    print(f"📄 合并字符集: {MERGED_CHARS_FILE.resolve()}")

    for font_path in INPUT_FONTS:
        if not font_path.is_file():
            print(f"⚠️ 字体不存在，跳过: {font_path}")
            continue
        subset_font(font_path, MERGED_CHARS_FILE)
