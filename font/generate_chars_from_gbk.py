# -*- coding: utf-8 -*-
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EXTRA_CHARS_FILE = BASE_DIR / "extra_chars.txt"
OUTPUT_FILE = BASE_DIR / "chars.txt"


def append_unique(chars, seen, text):
    for ch in text:
        if ch in "\r\n\t":
            continue
        if ch not in seen:
            chars.append(ch)
            seen.add(ch)


def iter_gbk_chars():
    # Single-byte ASCII range.
    for code in range(0x20, 0x7F):
        yield bytes([code]).decode("gbk")

    # GBK double-byte range:
    # first byte 0x81-0xFE, second byte 0x40-0xFE except 0x7F.
    for high in range(0x81, 0xFF):
        for low in range(0x40, 0xFF):
            if low == 0x7F:
                continue
            try:
                yield bytes([high, low]).decode("gbk")
            except UnicodeDecodeError:
                continue


def main():
    chars = []
    seen = set()

    append_unique(chars, seen, "\u3000")

    for ch in iter_gbk_chars():
        append_unique(chars, seen, ch)

    if EXTRA_CHARS_FILE.exists():
        append_unique(chars, seen, EXTRA_CHARS_FILE.read_text(encoding="utf-8"))

    OUTPUT_FILE.write_text("".join(chars), encoding="utf-8")

    print(f"chars.txt generated: {OUTPUT_FILE}")
    print(f"character count: {len(chars)}")
    if EXTRA_CHARS_FILE.exists():
        print(f"extra chars loaded: {EXTRA_CHARS_FILE}")


if __name__ == "__main__":
    main()
