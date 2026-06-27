import subprocess
import os
import sys
import traceback


# ============================
# CONFIGURATION
# ============================
LOCAL_FILE = r"D:\apk\Fotile_HAL_Service"
DEVICE_DIR = "/mnt/UDISK"
PROCESS_NAME = "Fotile_HAL_Service"


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


# ============================
# CORE FUNCTIONS
# ============================
def select_device():
    """Select a device when multiple ADB devices are connected."""
    result = subprocess.run(
        "adb devices",
        shell=True,
        text=True,
        capture_output=True
    )

    lines = result.stdout.strip().splitlines()
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


def check_local_file():
    if not os.path.exists(LOCAL_FILE):
        print(f"[ERROR] Local file not found: {LOCAL_FILE}")
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"[OK] Local file exists: {LOCAL_FILE}")


def push_to_device(device_id):
    print(f"=== Push file to device [{device_id}] ===")
    print(f"Local : {LOCAL_FILE}")
    print(f"Device: {DEVICE_DIR}/")

    result = run_cmd(
        f'adb -s {device_id} push "{LOCAL_FILE}" "{DEVICE_DIR}/"'
    )

    if result.returncode != 0:
        print("[ERROR] adb push failed.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[OK] Push completed.")


def kill_old_process(device_id):
    print(f"=== Kill old process [{PROCESS_NAME}] if exists ===")

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
    print("=== Set executable permission ===")

    device_file = f"{DEVICE_DIR}/{os.path.basename(LOCAL_FILE)}"

    result = run_cmd(
        f'adb -s {device_id} shell "chmod 777 {device_file}"'
    )

    if result.returncode != 0:
        print("[ERROR] chmod failed.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[OK] chmod completed.")


def run_on_device(device_id):
    """Run the app on device in the same PowerShell window."""
    print(f"=== Launch {PROCESS_NAME} on device [{device_id}] ===")

    device_file_name = os.path.basename(LOCAL_FILE)

    process = subprocess.Popen(
        f'adb -s {device_id} shell "cd {DEVICE_DIR} && ./{device_file_name}"',
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
        print("\n[INFO] User interrupted. Killing device process...")
        kill_old_process(device_id)


# ============================
# MAIN ENTRY
# ============================
if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")

    try:
        print("========================================")
        print(" Push local Fotile_HAL_Service and run")
        print("========================================")

        check_local_file()

        device_id = select_device()

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