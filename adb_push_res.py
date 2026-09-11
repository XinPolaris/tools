import argparse
import subprocess
from pathlib import Path, PurePosixPath


# ---------- 配置 ----------
REMOTE_DIR = PurePosixPath("/mnt/app")
ADB_CMD = "adb"  # 如果 adb 不在 PATH 中，可改为 adb.exe 的完整路径
# --------------------------


def parse_args():
    """解析命令行中传入的待替换文件或文件夹。"""
    parser = argparse.ArgumentParser(
        description="将指定的文件或文件夹替换到设备的 /mnt/app 对应位置。"
    )
    parser.add_argument(
        "source",
        help="要替换的文件或文件夹路径；相对路径按当前工作目录解析。",
    )
    return parser.parse_args()


def resolve_source(source):
    """解析源路径，并计算它在设备上的相对路径。"""
    source_path = Path(source).expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"源路径不存在: {source_path}")
    if source_path.name.lower() == "res":
        raise ValueError("不能传入 res 根目录，请指定要替换的文件或子目录。")

    res_indexes = [
        index for index, part in enumerate(source_path.parts) if part.lower() == "res"
    ]
    if res_indexes:
        relative_path = Path(*source_path.parts[res_indexes[-1] + 1 :])
    else:
        relative_path = Path(source_path.name)

    return source_path, relative_path


def run_adb(*args):
    """执行 adb 命令，并在失败时抛出异常。"""
    subprocess.run([ADB_CMD, *map(str, args)], check=True)


def replace_res_item(source_path, relative_path):
    """删除设备上的对应目标，然后推送指定文件或目录。"""
    remote_path = REMOTE_DIR.joinpath(*relative_path.parts)
    remote_parent = remote_path.parent

    print(f"Replacing: {source_path} -> {remote_path}")
    run_adb("shell", "mkdir", "-p", remote_parent)
    run_adb("shell", "rm", "-rf", remote_path)
    run_adb("push", source_path, remote_parent)
    print("Replacement completed.")


def main():
    """校验用户输入并执行指定资源的替换。"""
    args = parse_args()
    source_path, relative_path = resolve_source(args.source)
    replace_res_item(source_path, relative_path)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Error: {error}") from error
