from fontTools.ttLib import TTFont

font = TTFont("SourceHanSansSC-Regular.otf")
font.save("SourceHanSansSC-Regular.ttf")

font = TTFont("SourceHanSansSC-Bold.otf")
font.save("SourceHanSansSC-Bold.ttf")
