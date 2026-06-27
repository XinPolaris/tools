# -*- coding: utf-8 -*-
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RECIPE_NAMES_FILE = BASE_DIR / "recipe_names.txt"
EXTRA_CHARS_FILE = BASE_DIR / "extra_chars.txt"
OUTPUT_FILE = BASE_DIR / "chars.txt"


BASE_CHARS = (
    "".join(chr(code) for code in range(0x20, 0x7F))
    + "　，。！？、；：“”‘’（）《》〈〉【】[]{}"
    + "·…—-～￥%℃°+*/=<>#&@|\\_^~"
)


def append_unique(chars, seen, text):
    for ch in text:
        if ch in "\r\n\t":
            continue
        if ch not in seen:
            chars.append(ch)
            seen.add(ch)


def main():
    if not RECIPE_NAMES_FILE.exists():
        raise FileNotFoundError(
            f"missing {RECIPE_NAMES_FILE}; put recipe names in it, one per line"
        )

    chars = []
    seen = set()

    append_unique(chars, seen, BASE_CHARS)
    append_unique(chars, seen, RECIPE_NAMES_FILE.read_text(encoding="utf-8"))

    if EXTRA_CHARS_FILE.exists():
        append_unique(chars, seen, EXTRA_CHARS_FILE.read_text(encoding="utf-8"))

    OUTPUT_FILE.write_text("".join(chars), encoding="utf-8")

    print(f"chars.txt generated: {OUTPUT_FILE}")
    print(f"character count: {len(chars)}")
    print(f"recipe names loaded: {RECIPE_NAMES_FILE}")
    if EXTRA_CHARS_FILE.exists():
        print(f"extra chars loaded: {EXTRA_CHARS_FILE}")


if __name__ == "__main__":
    main()
