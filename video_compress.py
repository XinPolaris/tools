import os
import subprocess
import sys
import shutil

# =========================
# 可配置参数（只改这里）
# =========================

# 是否去掉音频
REMOVE_AUDIO = False

# 目标视频码率（kbps）
VIDEO_BITRATE_KBPS = 400

# 目标帧率
TARGET_FPS = 30

# 视频编码器
VIDEO_CODEC = "libx264"

# 编码参数
X264_PRESET = "medium"   # ultrafast / fast / medium / slow
PIX_FMT = "yuv420p"

# =========================
# 尺寸控制（只限制最大宽）
# =========================

# 是否启用宽度限制
ENABLE_SCALE = True

# 最大允许宽度（像素）
MAX_WIDTH = 480

# =========================
# 支持的视频格式
# =========================

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}

# =========================
# 工具函数
# =========================

def is_video_file(filename):
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS

def recreate_dir(path):
    """
    如果目录存在则删除并重新创建
    """
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def build_ffmpeg_cmd(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
    ]

    # =========================
    # 仅限制最大宽度（超过才缩放）
    # =========================
    if ENABLE_SCALE and MAX_WIDTH:
        scale_expr = f"scale='if(gt(iw,{MAX_WIDTH}),{MAX_WIDTH},iw)':-2"
        cmd += ["-vf", scale_expr]

    # =========================
    # 编码参数
    # =========================
    cmd += [
        "-c:v", VIDEO_CODEC,
        "-b:v", f"{VIDEO_BITRATE_KBPS}k",
        "-r", str(TARGET_FPS),
        "-preset", X264_PRESET,
        "-pix_fmt", PIX_FMT,
    ]

    if REMOVE_AUDIO:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "copy"]

    cmd.append(output_path)
    return cmd

# =========================
# 主入口
# =========================

def main():
    if len(sys.argv) < 2:
        print("❌ 用法错误：")
        print("   python batch_compress_video.py <input_dir>")
        sys.exit(1)

    input_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(input_dir):
        print(f"❌ 输入路径不存在或不是文件夹：{input_dir}")
        sys.exit(1)

    output_dir = os.path.join(input_dir, "compress")

    # ⚠️ 如果输出目录存在，先删除再创建
    recreate_dir(output_dir)

    files = [
        f for f in os.listdir(input_dir)
        if is_video_file(f)
    ]

    if not files:
        print("❌ 输入目录中未找到视频文件")
        return

    print(f"🎬 输入目录：{input_dir}")
    print(f"📁 输出目录：{output_dir}")
    print(
        f"⚙️ 码率：{VIDEO_BITRATE_KBPS} kbps | "
        f"帧率：{TARGET_FPS} fps | "
        f"去音频：{REMOVE_AUDIO}"
    )
    print(f"📐 最大宽度限制：{MAX_WIDTH}px（仅超出才缩放）")
    print("-" * 60)

    for idx, filename in enumerate(files, 1):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        cmd = build_ffmpeg_cmd(input_path, output_path)

        print(f"[{idx}/{len(files)}] 处理：{filename}")
        print(" ".join(cmd))

        try:
            subprocess.run(cmd, check=True)
            print("✅ 完成\n")
        except subprocess.CalledProcessError:
            print("❌ 处理失败\n")

    print("🎉 所有视频处理完成")

if __name__ == "__main__":
    main()
