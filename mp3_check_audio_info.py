import subprocess
from pathlib import Path


# 要检测的 mp3 文件夹
AUDIO_DIR = r"D:\project_linux\04-ranghood-2\project_app\linux_app_fotile\project\04_hood\res\assest\offlineAudio"

# 递归检测子目录
RECURSIVE = True


def get_audio_info(file_path: Path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "default=noprint_wrappers=1",
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

    info = {
        "codec": "",
        "sample_rate": "",
        "channels": ""
    }

    for line in result.stdout.splitlines():
        if line.startswith("codec_name="):
            info["codec"] = line.replace("codec_name=", "", 1)
        elif line.startswith("sample_rate="):
            info["sample_rate"] = line.replace("sample_rate=", "", 1)
        elif line.startswith("channels="):
            info["channels"] = line.replace("channels=", "", 1)

    return info


def main():
    audio_dir = Path(AUDIO_DIR)

    if not audio_dir.exists():
        print(f"目录不存在: {audio_dir}")
        return

    files = list(audio_dir.rglob("*.mp3"))

    if not files:
        print(f"未找到 mp3 文件: {audio_dir}")
        return

    for file_path in files:
        info = get_audio_info(file_path)

        print(
            f"{file_path.relative_to(audio_dir)} | "
            f"编码: {info['codec']} | "
            f"采样率: {info['sample_rate']} | "
            f"声道: {info['channels']}"
        )


if __name__ == "__main__":
    main()