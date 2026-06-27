import subprocess
from pathlib import Path


# 要检测的视频目录
VIDEO_DIR = r"D:\project_linux\04-ranghood-2\project_app\linux_app_fotile\project\04_hood\res\video"

# 是否递归检测子目录
RECURSIVE = False


def check_audio(file_path: Path):
    """
    返回:
    {
        "has_audio": True/False,
        "codec": "aac",
        "sample_rate": "44100",
        "channels": "2"
    }
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index,codec_name,channels,sample_rate",
        "-of", "default=noprint_wrappers=1",
        str(file_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
    except FileNotFoundError:
        raise RuntimeError("未找到 ffprobe，请确认 ffmpeg/ffprobe 已加入环境变量 PATH")

    output = result.stdout.strip()

    if not output:
        return {
            "has_audio": False,
            "codec": "",
            "sample_rate": "",
            "channels": ""
        }

    info = {
        "has_audio": True,
        "codec": "",
        "sample_rate": "",
        "channels": ""
    }

    for line in output.splitlines():
        if line.startswith("codec_name="):
            info["codec"] = line.replace("codec_name=", "", 1)
        elif line.startswith("sample_rate="):
            info["sample_rate"] = line.replace("sample_rate=", "", 1)
        elif line.startswith("channels="):
            info["channels"] = line.replace("channels=", "", 1)

    return info


def main():
    video_dir = Path(VIDEO_DIR)

    if not video_dir.exists():
        print(f"目录不存在: {video_dir}")
        return

    if RECURSIVE:
        mp4_files = list(video_dir.rglob("*.mp4"))
    else:
        mp4_files = list(video_dir.glob("*.mp4"))

    if not mp4_files:
        print(f"目录下没有 mp4 文件: {video_dir}")
        return

    for file_path in mp4_files:
        try:
            audio_info = check_audio(file_path)

            has_audio_text = "是" if audio_info["has_audio"] else "否"

            print(
                f"{file_path.name} | "
                f"有音轨: {has_audio_text} | "
                f"编码: {audio_info['codec']} | "
                f"采样率: {audio_info['sample_rate']} | "
                f"声道: {audio_info['channels']}"
            )

        except Exception as e:
            print(f"{file_path.name} | 检测失败: {e}")

    print()
    print("检测完成")


if __name__ == "__main__":
    main()