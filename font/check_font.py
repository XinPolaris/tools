from fontTools.ttLib import TTFont

font_paths = [
    r"C:\tools\font\cut\OPPOSans-S-M-0802.ttf",
    r"C:\tools\font\cut\OPPOSans-S-M-0802.ttf",
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
