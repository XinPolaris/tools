import json
import subprocess
from pathlib import Path


VIDEO_DIR = r"D:\apk\navVideo"

RECURSIVE = False

VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv",
    ".ts", ".m2ts", ".webm", ".3gp", ".wmv"
}


def run_ffprobe(file_path: Path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(file_path)
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    if result.returncode != 0:
        return None, result.stderr.strip()

    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as e:
        return None, f"JSON解析失败: {e}"


def safe_get(data, key, default="-"):
    value = data.get(key, default)
    if value in ("N/A", "", None):
        return default
    return value


def format_duration(seconds_str):
    try:
        seconds = float(seconds_str)
    except Exception:
        return "-"

    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


def format_bitrate(bit_rate_str):
    try:
        bit_rate = int(bit_rate_str)
    except Exception:
        return "-"

    if bit_rate >= 1_000_000:
        return f"{bit_rate / 1_000_000:.2f} Mbps"
    elif bit_rate >= 1_000:
        return f"{bit_rate / 1_000:.2f} Kbps"
    return f"{bit_rate} bps"


def calc_fps(fps_str):
    if not fps_str or fps_str == "N/A":
        return "-"

    try:
        if "/" in fps_str:
            a, b = fps_str.split("/", 1)
            fps = float(a) / float(b)
        else:
            fps = float(fps_str)

        return f"{fps:.2f}"
    except Exception:
        return fps_str


def get_video_files(video_dir: Path):
    if RECURSIVE:
        files = video_dir.rglob("*")
    else:
        files = video_dir.glob("*")

    return [
        f for f in files
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS
    ]


def print_video_info(file_path: Path):
    data, error = run_ffprobe(file_path)

    print("=" * 80)
    print(f"文件: {file_path}")

    if error:
        print(f"读取失败: {error}")
        return

    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    print(f"大小: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"封装格式: {safe_get(fmt, 'format_name')}")
    print(f"时长: {format_duration(safe_get(fmt, 'duration'))}")
    print(f"总码率: {format_bitrate(safe_get(fmt, 'bit_rate'))}")

    if video_streams:
        for i, v in enumerate(video_streams):
            print()
            print(f"[视频流 {i}]")
            print(f"编码: {safe_get(v, 'codec_name')}")
            print(f"编码详情: {safe_get(v, 'codec_long_name')}")
            print(f"分辨率: {safe_get(v, 'width')}x{safe_get(v, 'height')}")
            print(f"帧率 avg_frame_rate: {calc_fps(safe_get(v, 'avg_frame_rate'))} fps")
            print(f"帧率 r_frame_rate: {calc_fps(safe_get(v, 'r_frame_rate'))} fps")
            print(f"像素格式: {safe_get(v, 'pix_fmt')}")
            print(f"Profile: {safe_get(v, 'profile')}")
            print(f"Level: {safe_get(v, 'level')}")
            print(f"视频码率: {format_bitrate(safe_get(v, 'bit_rate'))}")
            print(f"视频帧数: {safe_get(v, 'nb_frames')}")
    else:
        print()
        print("[视频流]")
        print("未检测到视频流")

    if audio_streams:
        for i, a in enumerate(audio_streams):
            print()
            print(f"[音频流 {i}]")
            print(f"编码: {safe_get(a, 'codec_name')}")
            print(f"编码详情: {safe_get(a, 'codec_long_name')}")
            print(f"采样率: {safe_get(a, 'sample_rate')} Hz")
            print(f"声道数: {safe_get(a, 'channels')}")
            print(f"声道布局: {safe_get(a, 'channel_layout')}")
            print(f"音频码率: {format_bitrate(safe_get(a, 'bit_rate'))}")
    else:
        print()
        print("[音频流]")
        print("未检测到音频流")


def main():
    video_dir = Path(VIDEO_DIR)

    if not video_dir.exists():
        print(f"目录不存在: {video_dir}")
        return

    files = get_video_files(video_dir)

    if not files:
        print(f"未找到视频文件: {video_dir}")
        return

    print(f"共找到 {len(files)} 个视频文件")

    for file_path in files:
        print_video_info(file_path)


if __name__ == "__main__":
    main()