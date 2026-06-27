#!/usr/bin/env python3
"""
批量按比例（只指定宽，按原尺寸比例缩放）修改输入文件夹内所有图片尺寸。

依赖:
    pip install pillow

用法示例:
    python resize_images.py /path/to/input 800
    python resize_images.py /path/to/input 800 --output /path/to/output --recursive --no-upscale
    python resize_images.py /path/to/input 800 --inplace

说明:
    - 必须给出目标宽度（像素）。高度按原图纵横比计算并取整。
    - 默认会把处理后的图片写入 output 子目录 (input/resized_by_width_<width>)，除非使用 --inplace 覆盖原图。
    - 可选递归处理子目录（--recursive）。
    - 可选阻止放大（--no-upscale）。
    - 会尽量保留格式与透明度，跳过动画 GIF（可修改代码以处理动画）。
"""

import argparse
import os
import sys
from PIL import Image, ImageOps, UnidentifiedImageError

COMMON_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}


def parse_args():
    p = argparse.ArgumentParser(description="按给定宽度按比例批量缩放图片（只指定宽，保持纵横比）")
    p.add_argument('input', help='输入文件夹路径（会处理该目录下的图片）')
    p.add_argument('width', type=int, help='目标宽度（像素）')
    p.add_argument('--output', '-o', help='输出文件夹（默认在输入文件夹下创建 resized_by_width_<width>）')
    p.add_argument('--inplace', action='store_true', help='就地覆盖原文件（谨慎使用）')
    p.add_argument('--recursive', '-r', action='store_true', help='递归处理子目录')
    p.add_argument('--no-upscale', action='store_true', help='禁止放大：当目标宽大于原始宽时跳过该图')
    p.add_argument('--quality', type=int, default=85, help='保存 JPEG 的质量（1-100），默认 85')
    p.add_argument('--extensions', nargs='*', help='只处理指定扩展名，例如: --extensions .jpg .png ，默认常见图像格式')
    return p.parse_args()


def collect_files(input_dir, recursive, exts):
    files = []
    if recursive:
        for root, dirs, filenames in os.walk(input_dir):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in exts:
                    files.append(os.path.join(root, fn))
    else:
        for fn in os.listdir(input_dir):
            full = os.path.join(input_dir, fn)
            if os.path.isfile(full) and os.path.splitext(fn)[1].lower() in exts:
                files.append(full)
    return sorted(files)


def calc_new_size(img, target_width, no_upscale):
    orig_w, orig_h = img.size
    if no_upscale and target_width >= orig_w:
        return None  # signal to skip
    new_h = max(1, int(round((target_width * orig_h) / orig_w)))
    return (target_width, new_h)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def process_one(path, out_path, width, no_upscale, quality, inplace):
    try:
        with Image.open(path) as im:
            # correct orientation from EXIF if present
            im = ImageOps.exif_transpose(im)
            fmt = im.format  # original format, may be None
            # skip animated gifs (optional)
            if fmt == 'GIF' and getattr(im, "is_animated", False):
                print(f"跳过动画 GIF: {path}")
                return False

            new_size = calc_new_size(im, width, no_upscale)
            if new_size is None:
                print(f"跳过（禁止放大且目标宽 >= 原宽）: {path}")
                return False

            # if size is same, still copy/save depending on inplace
            if im.size == new_size and not inplace:
                # 如果尺寸相同且不就地覆盖，直接复制文件到输出位置
                from shutil import copy2
                ensure_dir(os.path.dirname(out_path))
                copy2(path, out_path)
                print(f"尺寸相同，复制: {path} -> {out_path}")
                return True

            # convert mode if needed for saving
            # preserve transparency for PNG/WebP by keeping mode with alpha
            resample = Image.LANCZOS
            resized = im.resize(new_size, resample=resample)

            ensure_dir(os.path.dirname(out_path))

            save_kwargs = {}
            if fmt in ('JPEG', 'JPG'):
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True
                # ensure no alpha for JPEG
                if resized.mode in ('RGBA', 'LA'):
                    resized = resized.convert('RGB')
            elif fmt == 'PNG':
                save_kwargs['optimize'] = True
            # For other formats, let PIL choose defaults

            # If format is None (unknown), infer from extension of out_path
            out_ext = os.path.splitext(out_path)[1].lower()
            if fmt is None:
                fmt_map = {
                    '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG',
                    '.gif': 'GIF', '.bmp': 'BMP', '.tiff': 'TIFF', '.webp': 'WEBP'
                }
                fmt = fmt_map.get(out_ext, None)

            # Save. If inplace, write to a temp file then replace to avoid truncation on error.
            if inplace:
                import tempfile
                tmpfd, tmppath = tempfile.mkstemp(suffix=os.path.splitext(out_path)[1], dir=os.path.dirname(out_path))
                os.close(tmpfd)
                try:
                    resized.save(tmppath, format=fmt, **save_kwargs) if fmt else resized.save(tmppath, **save_kwargs)
                    os.replace(tmppath, out_path)
                finally:
                    if os.path.exists(tmppath):
                        try:
                            os.remove(tmppath)
                        except Exception:
                            pass
            else:
                resized.save(out_path, format=fmt, **save_kwargs) if fmt else resized.save(out_path, **save_kwargs)

            print(f"已处理: {path} -> {out_path} ({new_size[0]}x{new_size[1]})")
            return True
    except UnidentifiedImageError:
        print(f"不是图片文件或无法识别: {path}")
    except Exception as e:
        print(f"处理失败: {path}，错误: {e}")
    return False


def main():
    args = parse_args()
    input_path = os.path.abspath(args.input)

    # ✅ 新增：支持单文件
    if os.path.isfile(input_path):
        files = [input_path]
        input_dir = os.path.dirname(input_path)
    elif os.path.isdir(input_path):
        input_dir = input_path
        exts = set([e.lower() for e in (args.extensions if args.extensions else COMMON_EXTS)])
        files = collect_files(input_dir, args.recursive, exts)
    else:
        print("输入路径不存在:", input_path)
        sys.exit(1)

    if not files:
        print("未找到图片文件。")
        sys.exit(0)

    if args.inplace:
        output_root = input_dir
    else:
        if args.output:
            output_root = os.path.abspath(args.output)
        else:
            output_root = os.path.join(input_dir, f"resized_by_width_{args.width}")

    total = len(files)
    succeeded = 0

    for i, f in enumerate(files, 1):
        # ✅ 单文件时不要带相对路径层级
        if os.path.isfile(input_path):
            out_file = os.path.join(output_root, os.path.basename(f))
        else:
            rel = os.path.relpath(f, start=input_dir)
            out_file = os.path.join(output_root, rel)

        if args.inplace:
            out_file = f

        ok = process_one(f, out_file, args.width, args.no_upscale, args.quality, args.inplace)
        if ok:
            succeeded += 1

    print(f"完成：共找到 {total} 张，成功处理 {succeeded} 张，失败/跳过 {total - succeeded} 张。 输出目录: {output_root}")



if __name__ == '__main__':
    main()