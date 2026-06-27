import subprocess
import sys

def print_keyframes(video_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v",
        "-show_entries", "frame=best_effort_timestamp_time,pict_type",
        "-of", "csv=p=0",
        video_path
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("ffprobe error:", e.stderr)
        return

    for line in result.stdout.splitlines():
        parts = line.strip().split(",")

        if len(parts) != 2:
            continue

        time_str, pict_type = parts

        if pict_type != "I":
            continue

        if time_str == "N/A":
            continue

        try:
            ms = float(time_str) * 1000
            print(f"{ms:.3f} ms")
        except ValueError:
            continue


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <video_file>")
        sys.exit(1)

    print_keyframes(sys.argv[1])