import argparse
import shutil
import subprocess
import sys


PROCESS_NAME = "Fotile_HAL_Service"


def run_adb(device_id, *args, capture_output=False):
    """执行指定设备上的 ADB 命令。"""
    return subprocess.run(
        ["adb", "-s", device_id, *args],
        text=True,
        capture_output=capture_output,
    )


def get_connected_devices():
    """获取当前处于可用状态的 ADB 设备列表。"""
    result = subprocess.run(
        ["adb", "devices"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "[ERROR] Failed to query ADB devices.")
        sys.exit(1)

    return [
        line.split()[0]
        for line in result.stdout.splitlines()[1:]
        if len(line.split()) >= 2 and line.split()[1] == "device"
    ]


def select_device(requested_device):
    """选择命令行指定的设备，未指定时要求仅连接一台设备。"""
    devices = get_connected_devices()
    if requested_device:
        if requested_device not in devices:
            print(f"[ERROR] ADB device is unavailable: {requested_device}")
            sys.exit(1)
        return requested_device

    if not devices:
        print("[ERROR] No available ADB device.")
        sys.exit(1)
    if len(devices) > 1:
        print("[ERROR] Multiple ADB devices found. Specify one with --serial:")
        for device_id in devices:
            print(f"  {device_id}")
        sys.exit(1)
    return devices[0]


def stop_service(device_id):
    """查找并强制停止设备上的中间件进程。"""
    result = run_adb(
        device_id,
        "shell",
        "pidof",
        PROCESS_NAME,
        capture_output=True,
    )
    pids = result.stdout.split()
    if not pids:
        print(f"[INFO] {PROCESS_NAME} is not running.")
        return

    print(f"[INFO] Stopping {PROCESS_NAME}: {' '.join(pids)}")
    for pid in pids:
        result = run_adb(device_id, "shell", "kill", "-9", pid)
        if result.returncode != 0:
            print(f"[ERROR] Failed to stop PID {pid}.")
            sys.exit(1)


def start_service_with_uart_log(device_id):
    """以前台模式启动中间件，并向其控制台发送 UART 日志开启命令。"""
    print(f"[INFO] Starting {PROCESS_NAME} with manual mode and UART logging enabled.")
    print("[INFO] Press Ctrl+C to stop the foreground session.")
    process = subprocess.Popen(
        [
            "adb",
            "-s",
            device_id,
            "shell",
            PROCESS_NAME,
            "manual=1",
        ],
        stdin=subprocess.PIPE,
    )

    try:
        process.stdin.write(b"smart uartlog 1\n")
        process.stdin.flush()
        process.stdin.close()
        return_code = process.wait()
    except KeyboardInterrupt:
        print("\n[INFO] Foreground session interrupted.")
        return

    if return_code != 0:
        print(f"[ERROR] {PROCESS_NAME} exited with code {return_code}.")
        sys.exit(return_code)


def main():
    """解析参数并依次执行进程重启和日志开启操作。"""
    parser = argparse.ArgumentParser(
        description="Restart Fotile_HAL_Service and enable UART logging."
    )
    parser.add_argument("-s", "--serial", help="ADB device serial")
    args = parser.parse_args()

    if shutil.which("adb") is None:
        print("[ERROR] adb was not found in PATH.")
        sys.exit(1)

    device_id = select_device(args.serial)
    print(f"[INFO] Using ADB device: {device_id}")
    stop_service(device_id)
    start_service_with_uart_log(device_id)


if __name__ == "__main__":
    main()
