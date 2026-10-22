import subprocess
import sys

def get_keyframes(video_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_frames",
        "-show_entries", "frame=key_frame,best_effort_timestamp_time",
        "-of", "csv=p=0",
        video_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    keyframes = []

    for line in result.stdout.splitlines():
        parts = line.strip().split(",")
        if len(parts) != 2:
            continue
        key_flag, timestamp = parts
        if key_flag != '1':
            continue
        keyframes.append(float(timestamp))

    return keyframes

def find_seek_frame(keyframes, target_time):
    seek_frame = max((kf for kf in keyframes if kf <= target_time), default=None)
    return seek_frame

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python script.py 视频文件 [seek时间]")
        sys.exit(1)

    video = sys.argv[1]
    keyframes = get_keyframes(video)
    print("关键帧时间列表（秒）：")
    for kf in keyframes:
        print(f"{kf:.3f}s")

    if len(sys.argv) >= 3:
        target = float(sys.argv[2])
        frame = find_seek_frame(keyframes, target)
        print(f"\nseek({target}s) 会落在关键帧: {frame:.3f}s")
