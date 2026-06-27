import paramiko
import subprocess
import os
import sys
import time
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
REMOTE_PORT = 22
REMOTE_USER = "huangx"
REMOTE_PASS = "1"

REMOTE_PROJECT_DIR = "/home/huangx/project/04-ranghood"
REMOTE_FILE = "/home/huangx/project/04-ranghood/FIKS_OS_LINUX"

BUILD_CMD = "./fotile_make.sh lunch_project=19 lunch_compile_type=3 ccache=y"

LOCAL_FILE = r"D:\apk\FIKS_OS_LINUX"
DEVICE_DIR = "/mnt/UDISK"
PROCESS_NAME = "FIKS_OS_LINUX"


# ============================
# UTILS
# ============================
def pause_exit(code=1):
    input("Press Enter to exit...")
    sys.exit(code)


def run_cmd(cmd):
    """Run a local shell command and print stdout/stderr."""
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)

    if result.stdout.strip():
        print(result.stdout.strip())

    if result.stderr.strip():
        print(result.stderr.strip())

    return result


def format_time(ts):
    if ts is None or ts <= 0:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    
def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


# ============================
# REMOTE FUNCTIONS
# ============================
def connect_ssh():
    print(f"=== Connect remote server: {REMOTE_USER}@{REMOTE_HOST} ===")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname=REMOTE_HOST,
        port=REMOTE_PORT,
        username=REMOTE_USER,
        password=REMOTE_PASS,
        timeout=15,
        look_for_keys=False,
        allow_agent=False
    )

    print("[OK] SSH connected.")
    return ssh


def remote_exec_simple(ssh, cmd):
    """Execute remote command and return stdout/stderr/exit_status."""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore").strip()
    err = stderr.read().decode("utf-8", errors="ignore").strip()
    status = stdout.channel.recv_exit_status()
    return out, err, status


def get_remote_file_mtime(ssh):
    """
    Get remote file modify time.
    Return:
        int timestamp if file exists
        0 if file not exists
    """
    cmd = f'if [ -f "{REMOTE_FILE}" ]; then stat -c %Y "{REMOTE_FILE}"; else echo 0; fi'
    out, err, status = remote_exec_simple(ssh, cmd)

    if status != 0:
        print("[ERROR] Failed to get remote file mtime.")
        if err:
            print(err)
        raise RuntimeError("get remote file mtime failed")

    try:
        return int(out.strip())
    except ValueError:
        print("[ERROR] Invalid mtime output:", out)
        raise


def run_remote_build(ssh):
    """
    Run build command on remote server and stream output to local PowerShell.
    """
    print()
    print("=== Remote build start ===")
    print(f"[REMOTE] cd {REMOTE_PROJECT_DIR}")
    print(f"[REMOTE] {BUILD_CMD}")
    print()

    full_cmd = f'cd "{REMOTE_PROJECT_DIR}" && {BUILD_CMD}'

    transport = ssh.get_transport()
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command(full_cmd)

    try:
        while True:
            if channel.recv_ready():
                data = channel.recv(4096)
                if data:
                    print(data.decode("utf-8", errors="ignore"), end="")

            if channel.recv_stderr_ready():
                data = channel.recv_stderr(4096)
                if data:
                    print(data.decode("utf-8", errors="ignore"), end="")

            if channel.exit_status_ready():
                while channel.recv_ready():
                    data = channel.recv(4096)
                    if data:
                        print(data.decode("utf-8", errors="ignore"), end="")
                while channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096)
                    if data:
                        print(data.decode("utf-8", errors="ignore"), end="")
                break

            time.sleep(0.1)

        exit_status = channel.recv_exit_status()
        print()
        print(f"=== Remote build finished, exit code: {exit_status} ===")

        if exit_status != 0:
            raise RuntimeError(f"Remote build failed, exit code: {exit_status}")

    finally:
        channel.close()


def download_from_remote():
    print()
    print(f"=== Download from {REMOTE_HOST}: {REMOTE_FILE} ===")

    try:
        os.makedirs(os.path.dirname(LOCAL_FILE), exist_ok=True)

        transport = paramiko.Transport((REMOTE_HOST, REMOTE_PORT))
        print("Connecting to remote server for SFTP...")
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


def build_and_check_update():
    """
    1. SSH login
    2. Get old mtime
    3. Build
    4. Get new mtime
    5. If not changed, skip install
    6. Close SSH before local install
    """
    ssh = None

    try:
        ssh = connect_ssh()

        old_mtime = get_remote_file_mtime(ssh)
        print(f"[INFO] Before build mtime: {old_mtime} ({format_time(old_mtime)})")

        run_remote_build(ssh)

        new_mtime = get_remote_file_mtime(ssh)
        print(f"[INFO] After build mtime : {new_mtime} ({format_time(new_mtime)})")

        if new_mtime <= 0:
            print("[ERROR] Build finished, but remote FIKS_OS_LINUX does not exist.")
            return False

        if new_mtime == old_mtime:
            print()
            print("[SKIP] FIKS_OS_LINUX modify time not changed.")
            print("[SKIP] No need to download or install.")
            return False

        print()
        print("[OK] FIKS_OS_LINUX has been updated.")
        print("[OK] Will logout remote server and continue local install.")
        return True

    except Exception as e:
        print("[ERROR] Remote build/check failed:", e)
        traceback.print_exc()
        pause_exit(1)

    finally:
        if ssh:
            ssh.close()
            print("[OK] SSH disconnected.")


# ============================
# ADB FUNCTIONS
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


def push_to_device(device_id):
    print()
    print(f"=== Push file to device [{device_id}] ===")
    result = run_cmd(f'adb -s {device_id} push "{LOCAL_FILE}" "{DEVICE_DIR}"')

    if result.returncode != 0:
        print("[ERROR] adb push failed.")
        pause_exit(1)


def kill_old_process(device_id):
    print()
    print(f"=== Kill old process on [{device_id}] if exists ===")

    result = subprocess.run(
        f'adb -s {device_id} shell "pgrep {PROCESS_NAME}"',
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
    print()
    print(f"=== Set executable permission on [{device_id}] ===")

    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"
    result = run_cmd(f'adb -s {device_id} shell "chmod 777 {device_file}"')

    if result.returncode != 0:
        print("[ERROR] chmod failed.")
        pause_exit(1)


def run_on_device(device_id):
    """Run the app on device in the same PowerShell window, preserving colors."""
    print()
    print(f"=== Launch app on [{device_id}] in current PowerShell window ===")

    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"

    process = subprocess.Popen(
        f'adb -s {device_id} shell "{device_file}"',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1
    )

    try:
        for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="ignore")
            print(line, end="")

        process.wait()

    except KeyboardInterrupt:
        print("\n[INFO] User interrupted. Killing local adb shell process...")
        process.terminate()
        process.wait()


def install_to_device():
    clear_console()
    device_id = select_device()
    download_from_remote()
    push_to_device(device_id)
    kill_old_process(device_id)
    set_executable(device_id)
    run_on_device(device_id)


# ============================
# MAIN ENTRY
# ============================
if __name__ == "__main__":
    clear_console()

    try:
        print("========================================")
        print(" Build on remote server, then install")
        print("========================================")

        need_install = build_and_check_update()

        if not need_install:
            print()
            print("=== Finished: no install needed ===")
            sys.exit(0)

        install_to_device()

        print()
        print("=== All steps completed ===")
        sys.exit(0)

    except Exception as e:
        print("[FATAL ERROR] Unexpected exception:", e)
        traceback.print_exc()
        pause_exit(1)