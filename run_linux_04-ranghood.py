import paramiko
import subprocess
import os
import sys
import traceback
from colorama import init

# ============================
# INIT
# ============================
# 启用 Windows PowerShell 的 ANSI 支持
init()

# ============================
# CONFIGURATION
# ============================
REMOTE_HOST = "10.49.3.18"
REMOTE_USER = "huangx"
REMOTE_PASS = "1"
REMOTE_FILE = "/home/huangx/project/04-ranghood-2/FIKS_OS_LINUX"
LOCAL_FILE = r"D:\apk\FIKS_OS_LINUX"
DEVICE_DIR = "/mnt/UDISK"
PROCESS_NAME = "FIKS_OS_LINUX"


# ============================
# UTILS
# ============================
def run_cmd(cmd):
    """Run a shell command and print stdout/stderr."""
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result


def pause_exit(code=1):
    input("Press Enter to exit...")
    sys.exit(code)


# ============================
# CORE FUNCTIONS
# ============================
def select_device():
    """Select a device when multiple ADB devices are connected."""
    result = subprocess.run("adb devices", shell=True, text=True, capture_output=True)
    lines = result.stdout.strip().splitlines()
    devices = [line.split()[0] for line in lines if "\tdevice" in line]

    if not devices:
        print("[ERROR] No ADB devices found.")
        pause_exit(1)

    if len(devices) == 1:
        print(f"[INFO] Using single device: {devices[0]}")
        return devices[0]

    print("Multiple devices detected:")
    for i, d in enumerate(devices, 1):
        print(f"  {i}. {d}")

    while True:
        try:
            choice = int(input("Select device number: "))
            if 1 <= choice <= len(devices):
                selected = devices[choice - 1]
                print(f"[INFO] Selected device: {selected}")
                return selected
        except ValueError:
            pass
        print("Invalid selection, please try again.")


def download_from_remote():
    print(f"=== Download from {REMOTE_HOST}: {REMOTE_FILE} ===")
    try:
        os.makedirs(os.path.dirname(LOCAL_FILE), exist_ok=True)
        transport = paramiko.Transport((REMOTE_HOST, 22))
        print("Connecting to remote server...")
        transport.connect(username=REMOTE_USER, password=REMOTE_PASS)
        print("Connected. Start downloading...")

        sftp = paramiko.SFTPClient.from_transport(transport)

        try:
            file_stat = sftp.stat(REMOTE_FILE)
            total_size = file_stat.st_size
        except FileNotFoundError:
            raise FileNotFoundError(f"Remote file not found: {REMOTE_FILE}")

        def progress(transferred, total):
            percent = transferred * 100 / total if total else 0
            mb_done = transferred / 1024 / 1024
            mb_total = total / 1024 / 1024 if total else 0
            print(
                f"\rDownloading: {mb_done:.2f} MB / {mb_total:.2f} MB  ({percent:.2f}%)",
                end="",
                flush=True
            )

        sftp.get(REMOTE_FILE, LOCAL_FILE, callback=progress)
        print()

        sftp.close()
        transport.close()
        print(f"[OK] Download completed: {LOCAL_FILE}")

    except Exception as e:
        print("[ERROR] Download failed:", e)
        traceback.print_exc()
        pause_exit(1)
        
def remove_old_log(device_id):
    print(f"Removing old log on [{device_id}] ...")
    run_cmd(
        f'adb -s {device_id} shell "rm -f /tmp/cache/fiks/log.txt"'
    )

def push_to_device(device_id):
    print(f"Pushing file to device [{device_id}] ...")
    result = run_cmd(f'adb -s {device_id} push "{LOCAL_FILE}" "{DEVICE_DIR}"')
    if result.returncode != 0:
        print("[ERROR] adb push failed")
        pause_exit(1)


def kill_old_process(device_id):
    print(f"Killing old process on [{device_id}] if exists...")
    result = subprocess.run(
        f'adb -s {device_id} shell "pidof {PROCESS_NAME} 2>/dev/null || pgrep -f {PROCESS_NAME} 2>/dev/null"',
        shell=True,
        text=True,
        capture_output=True
    )
    pids = result.stdout.strip().splitlines()
    if not pids:
        print("[INFO] No old process found.")
        return

    for pid in pids:
        pid = pid.strip()
        if pid:
            print(f"Killing PID: {pid}")
            run_cmd(f'adb -s {device_id} shell "kill -9 {pid}"')


def set_executable(device_id):
    print(f"Setting executable permission on [{device_id}] ...")
    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"
    result = run_cmd(f'adb -s {device_id} shell "chmod 777 {device_file}"')
    if result.returncode != 0:
        print("[ERROR] chmod failed.")
        pause_exit(1)


def print_device_log_tail(device_id):
    print("=== Device log tail: /tmp/cache/fiks/log.txt ===")
    result = run_cmd(
        f'adb -s {device_id} shell "if [ -f /tmp/cache/fiks/log.txt ]; then tail -n 80 /tmp/cache/fiks/log.txt; else echo log file not found; fi"'
    )
    if result.returncode != 0:
        print("[WARN] Failed to read device log.")


def run_on_device(device_id):
    """Run the app on device in the same PowerShell window, preserving colors."""
    print(f"Launching app on [{device_id}] in current window...")
    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"

    # 直接在终端运行，不捕获输出，允许交互式使用
    try:
        subprocess.call(f'adb -s {device_id} shell "{device_file}"', shell=True)
    except KeyboardInterrupt:
        print("\n[INFO] User interrupted.")


def run_on_device(device_id):
    """Run the app on device in the same PowerShell window, preserving colors."""
    print(f"Launching app on [{device_id}] in current window...")
    device_file_name = os.path.basename(LOCAL_FILE)

    # Run from DEVICE_DIR because this app may load files by relative path.
    cmd = f'adb -s {device_id} shell "cd {DEVICE_DIR} && ./{device_file_name}"'
    try:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )

        for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="ignore")
            print(line, end="")

        return_code = process.wait()
        print(f"\n[INFO] App process exited, adb return code: {return_code}")
        print_device_log_tail(device_id)

        if return_code != 0:
            print("[ERROR] App launch failed or exited with error.")
            pause_exit(return_code)

        print("[WARN] App exited immediately. Check the log above for the reason.")
        pause_exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] User interrupted.")


# ============================
# MAIN ENTRY
# ============================
if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    
    try:
        device_id = select_device()
        download_from_remote()
        remove_old_log(device_id) #清除旧的日志
        push_to_device(device_id)
        kill_old_process(device_id)
        set_executable(device_id)
        run_on_device(device_id)
        print("=== All steps completed ===")
        sys.exit(0)
    except Exception as e:
        print("[FATAL ERROR] Unexpected exception:", e)
        traceback.print_exc()
        pause_exit(1)
