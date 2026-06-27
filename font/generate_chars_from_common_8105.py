# -*- coding: utf-8 -*-
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMMON_CHARS_FILE = BASE_DIR / "common_8105.txt"
EXTRA_CHARS_FILE = BASE_DIR / "extra_chars.txt"
OUTPUT_FILE = BASE_DIR / "chars.txt"


def append_unique(chars, seen, text):
    for ch in text:
        if ch in "\r\n\t":
            continue
        if ch not in seen:
            chars.append(ch)
            seen.add(ch)


def main():
    chars = []
    seen = set()

    # ASCII visible chars and half-width space.
    append_unique(chars, seen, "".join(chr(code) for code in range(0x20, 0x7F)))

    # Common full-width Chinese punctuation and symbols used in UI/copy.
    append_unique(
        chars,
        seen,
        "　，。！？、；：“”‘’（）《》〈〉【】[]{}"
        "·…—-～￥%℃°+*/=<>#&@|\\_^~",
    )

    append_unique(chars, seen, COMMON_CHARS_FILE.read_text(encoding="utf-8"))

    if EXTRA_CHARS_FILE.exists():
        append_unique(chars, seen, EXTRA_CHARS_FILE.read_text(encoding="utf-8"))

    OUTPUT_FILE.write_text("".join(chars), encoding="utf-8")

    print(f"chars.txt generated: {OUTPUT_FILE}")
    print(f"character count: {len(chars)}")
    print(f"common chars loaded: {COMMON_CHARS_FILE}")
    if EXTRA_CHARS_FILE.exists():
        print(f"extra chars loaded: {EXTRA_CHARS_FILE}")


if __name__ == "__main__":
    main()
