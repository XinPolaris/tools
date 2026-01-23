from fontTools.ttLib import TTFont

font_path = r"D:\apk\font\cut\OPPOSanSB.ttf"
font = TTFont(font_path)
cmap = font.getBestCmap()

check_chars = [" ", "\x20", "\u3000", "甄", "饪"]

for ch in check_chars:
    code = ord(ch)
    if code in cmap:
        print(f"{ch} 支持")
    else:
        print(f"{ch} 不支持")
