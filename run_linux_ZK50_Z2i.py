import paramiko
import subprocess
import os
import sys
import traceback

# ============================
# CONFIGURATION
# ============================
REMOTE_HOST = "10.49.3.18"
REMOTE_USER = "huangx"
REMOTE_PASS = "1"
REMOTE_FILE = "/home/huangx/ZK50_Z2i/FIKS_OS_LINUX"
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


def run_in_powershell(cmd):
    """Run command in a new PowerShell window and keep it open."""
    os.system(f'start powershell -NoExit -Command "{cmd}"')


# ============================
# CORE FUNCTIONS
# ============================
def select_device():
    """Select a device when multiple ADB devices are connected."""
    result = subprocess.run("adb devices", shell=True, text=True, capture_output=True)
    lines = result.stdout.strip().splitlines()

    # Skip header line "List of devices attached"
    devices = [line.split()[0] for line in lines if "\tdevice" in line]

    if not devices:
        print("[ERROR] No ADB devices found.")
        input("Press Enter to exit...")
        sys.exit(1)

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
        transport = paramiko.Transport((REMOTE_HOST, 22))
        print("Connecting to remote server...")
        transport.connect(username=REMOTE_USER, password=REMOTE_PASS)
        print("Connected. Start downloading...")
        sftp = paramiko.SFTPClient.from_transport(transport)

        try:
            sftp.stat(REMOTE_FILE)
        except FileNotFoundError:
            raise FileNotFoundError(f"Remote file not found: {REMOTE_FILE}")

        sftp.get(REMOTE_FILE, LOCAL_FILE)
        sftp.close()
        transport.close()
        print(f"[OK] Download completed: {LOCAL_FILE}")
    except Exception as e:
        print("[ERROR] Download failed:", e)
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)


def push_to_device(device_id):
    print(f"Pushing file to device [{device_id}] ...")
    result = run_cmd(f'adb -s {device_id} push "{LOCAL_FILE}" "{DEVICE_DIR}"')
    if result.returncode != 0:
        print("[ERROR] adb push failed")
        input("Press Enter to exit...")
        sys.exit(1)


def kill_old_process(device_id):
    print(f"Killing old process on [{device_id}] if exists...")
    result = subprocess.run(
        f'adb -s {device_id} shell "pgrep {PROCESS_NAME}"',
        shell=True,
        text=True,
        capture_output=True
    )
    pids = result.stdout.strip().splitlines()
    for pid in pids:
        pid = pid.strip()
        if pid:
            print(f"Killing PID: {pid}")
            run_cmd(f'adb -s {device_id} shell "kill -9 {pid}"')


def set_executable(device_id):
    print(f"Setting executable permission on [{device_id}] ...")
    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"
    run_cmd(f'adb -s {device_id} shell "chmod 777 {device_file}"')


def run_on_device(device_id):
    print(f"Launching app on [{device_id}] in a new PowerShell window...")
    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"
    run_in_powershell(f'adb -s {device_id} shell "{device_file}"')


# ============================
# MAIN ENTRY
# ============================
if __name__ == "__main__":
    try:
        device_id = select_device()
        download_from_remote()
        push_to_device(device_id)
        kill_old_process(device_id)
        set_executable(device_id)
        run_on_device(device_id)
        print("=== All steps completed ===")
        sys.exit(0)
    except Exception as e:
        print("[FATAL ERROR] Unexpected exception:", e)
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)
