import os
import subprocess
import sys


ADB_CMD = "adb"
LOCAL_FIX_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assest", "fiks_os_linux")
REMOTE_APP_DIR = "/mnt/app"
REMOTE_FIX_SCRIPT = "/etc/init.d/fiks_os_linux"
REMOTE_TEMP_SCRIPT = "/tmp/fiks_os_linux"
WRITE_TEST_FILE = f"{REMOTE_APP_DIR}/.adb_write_test"
WRITABLE_MARKER = "__MNT_APP_WRITABLE__"
READ_ONLY_MARKER = "__MNT_APP_READ_ONLY__"


def run_adb(*args, check=True, capture_output=False):
    return subprocess.run(
        [ADB_CMD, *args],
        check=check,
        text=True,
        capture_output=capture_output,
    )


def is_mnt_app_read_only():
    result = run_adb(
        "shell",
        f"if touch {WRITE_TEST_FILE} 2>/dev/null; then "
        f"rm -f {WRITE_TEST_FILE}; echo {WRITABLE_MARKER}; "
        f"else echo {READ_ONLY_MARKER}; fi",
        check=False,
        capture_output=True,
    )
    output = f"{result.stdout}\n{result.stderr}".strip()

    if WRITABLE_MARKER in output:
        return False
    if READ_ONLY_MARKER in output:
        return True

    raise RuntimeError(
        f"检查 {REMOTE_APP_DIR} 写权限失败（adb 返回码 {result.returncode}）：\n{output}"
    )


def replace_fix_script_and_reboot():
    print(f"推送修复脚本：{LOCAL_FIX_SCRIPT} -> {REMOTE_TEMP_SCRIPT}")
    run_adb("push", LOCAL_FIX_SCRIPT, REMOTE_TEMP_SCRIPT)

    print(f"替换 {REMOTE_FIX_SCRIPT}")
    run_adb(
        "shell",
        f"cp {REMOTE_TEMP_SCRIPT} {REMOTE_FIX_SCRIPT} && "
        f"chmod 755 {REMOTE_FIX_SCRIPT} && rm -f {REMOTE_TEMP_SCRIPT} && sync",
    )

    print("替换完成，正在重启设备……")
    run_adb("reboot")


def main():
    if not os.path.isfile(LOCAL_FIX_SCRIPT):
        raise FileNotFoundError(f"找不到本地修复脚本：{LOCAL_FIX_SCRIPT}")

    run_adb("wait-for-device")

    if not is_mnt_app_read_only():
        print(f"{REMOTE_APP_DIR} 可写，无需修复。")
        return

    print(f"检测到 {REMOTE_APP_DIR} 是只读文件系统。")
    replace_fix_script_and_reboot()


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"执行失败：{error}", file=sys.stderr)
        raise SystemExit(1)
