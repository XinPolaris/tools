from pathlib import Path
from fontTools.ttLib import TTFont

BASE_DIR = Path(__file__).resolve().parent

font_paths = [
    BASE_DIR / "output" / "OPPOSanSB.ttf",
    BASE_DIR / "output" / "OPPOSanSR.ttf",
]

check_chars = [" ", "\x20", "\u3000", "甄", "饪"]

for font_path in font_paths:
    print(f"\n字体：{font_path}")
    font = TTFont(font_path)
    cmap = font.getBestCmap()

    for ch in check_chars:
        if ord(ch) in cmap:
            print(f"{repr(ch)} 支持")
        else:
            print(f"{repr(ch)} 不支持")
