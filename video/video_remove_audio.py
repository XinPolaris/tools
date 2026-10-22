import subprocess
from pathlib import Path


VIDEO_DIR = Path(
    r"D:\project_linux\04-ranghood-2\project_app\linux_app_fotile\project\04_hood\res\video"
)

# 是否递归处理子目录
RECURSIVE = False

VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".flv",
    ".webm",
    ".ts",
    ".m4v",
}

# 白名单：这些文件不会处理，只写文件名即可
WHITELIST = {
    "timer_alarm.mp4"
    # "voice_listen.mp4",
}


def has_audio_stream(video_path: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(video_path),
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    return bool(result.stdout.strip())


def remove_audio(video_path: Path) -> bool:
    temp_path = video_path.with_name(video_path.stem + "_no_audio_tmp" + video_path.suffix)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-c:v", "copy",
        "-an",
        str(temp_path),
    ]

    print(f"\n处理: {video_path.name}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode != 0:
        print(f"失败: {video_path.name}")
        print(result.stderr)

        if temp_path.exists():
            temp_path.unlink()

        return False

    # 成功后直接替换原文件
    video_path.unlink()
    temp_path.rename(video_path)

    print(f"完成: {video_path.name}")
    return True


def main():
    if not VIDEO_DIR.exists():
        print(f"目录不存在: {VIDEO_DIR}")
        return

    pattern = "**/*" if RECURSIVE else "*"

    videos = [
        p for p in VIDEO_DIR.glob(pattern)
        if p.is_file()
        and p.suffix.lower() in VIDEO_EXTS
        and not p.name.endswith("_no_audio_tmp" + p.suffix)
    ]

    print(f"扫描目录: {VIDEO_DIR}")
    print(f"发现视频数量: {len(videos)}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for video in videos:
        if video.name in WHITELIST:
            print(f"跳过白名单: {video.name}")
            skip_count += 1
            continue

        if not has_audio_stream(video):
            print(f"无音轨，跳过: {video.name}")
            skip_count += 1
            continue

        if remove_audio(video):
            success_count += 1
        else:
            fail_count += 1

    print("\n========== 处理完成 ==========")
    print(f"成功处理: {success_count}")
    print(f"跳过文件: {skip_count}")
    print(f"失败文件: {fail_count}")


if __name__ == "__main__":
    main()