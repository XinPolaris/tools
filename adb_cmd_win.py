# 文件名：adb_cmd_win.py
import threading
import subprocess
from datetime import datetime
import time
import os

# 用户可修改此变量为自己的 Windows 用户名
USERNAME = "huangxina"

# 用户可修改此变量为需要操作的应用包名
PACKAGE_NAME = "com.fotile.fiks"

# 电脑路径模板
DOCUMENTS_PATH = f"D:\\{USERNAME}\\Documents"
PICTURES_PATH = f"D:\\{USERNAME}\\Pictures"
VIDEOS_PATH = f"D:\\{USERNAME}\\Videos"

commands = [
    (f"拉取 {PACKAGE_NAME} flog日志", "pull_logs"),
    ("实时 logcat 日志", "logcat"),
    ("跳转到设置", "adb shell am start -a android.settings.SETTINGS"),
    ("跳转到系统桌面", "adb shell am start -n com.android.launcher3/.Launcher"),
    (f"卸载 {PACKAGE_NAME}", f"adb uninstall {PACKAGE_NAME}"),
    (f"强制停止 {PACKAGE_NAME}", f"adb shell am force-stop {PACKAGE_NAME}"),
    ("重启", "adb reboot"),
    ("抓取 ANR 日志目录", "pull_anr"),
    ("系统操作码输入", "adb shell am start -n com.signway.signwaydoor/.MainActivity"),
    ("截屏到电脑", "screenshot"),
    ("录屏到电脑", "screenrecord"),
    (f"查看 {PACKAGE_NAME} 内存使用", f"adb shell dumpsys meminfo {PACKAGE_NAME}"),
    (f"查看 {PACKAGE_NAME} CPU 使用", f"adb shell top -n 1 | findstr {PACKAGE_NAME}"),
    ("恢复出厂设置", "adb shell am broadcast -a android.intent.action.MASTER_CLEAR"),
    ("退出脚本", "exit")
]

# 获取连接的设备列表
def get_connected_devices():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().splitlines()[1:]  # 跳过第一行
    devices = [line.split()[0] for line in lines if "device" in line]
    return devices

# 选择设备
def choose_device(devices):
    if len(devices) == 0:
        print("没有连接任何设备，请检查 adb 连接。")
        exit(1)
    elif len(devices) == 1:
        print(f"已自动选择设备: {devices[0]}")
        return devices[0]
    else:
        print("检测到多个设备，请选择一个设备：")
        for i, d in enumerate(devices, 1):
            print(f"{i}. {d}")
        while True:
            choice = input("输入序号: ")
            if choice.isdigit() and 1 <= int(choice) <= len(devices):
                return devices[int(choice) - 1]
            print("无效选择，请重新输入。")

# 执行 adb 命令，自动加上 -s 设备参数
def run_adb_command(cmd, device_id=None):
    if device_id:
        if cmd.startswith("adb "):
            cmd = f"adb -s {device_id} {cmd[4:]}"  # 替换 adb 开头
        else:
            cmd = f"adb -s {device_id} {cmd}"
    subprocess.run(cmd, shell=True)

def logcat_record(device_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_path = os.path.join(DOCUMENTS_PATH, f"logcat_{timestamp}.txt")

    # 启动 adb logcat 子进程
    cmd = ["adb", "-s", device_id, "logcat"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    print(f"开始记录 logcat 日志，保存到 {local_path}")
    print("按回车停止记录...")

    # 文件写入线程
    stop_flag = threading.Event()

    def write_log():
        with open(local_path, "w", encoding="utf-8") as f:
            for line in proc.stdout:
                if stop_flag.is_set():
                    break
                f.write(line)
                f.flush()

    thread = threading.Thread(target=write_log, daemon=True)
    thread.start()

    # 等待用户回车
    input()
    stop_flag.set()

    # 结束 logcat 进程
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

    thread.join()
    print(f"logcat 日志已保存到 {local_path}")

def main():
    device_id = choose_device(get_connected_devices())

    while True:

        # 菜单
        print("\n====== ADB 命令选择器 ======")
        for i, (desc, _) in enumerate(commands, 1):
            print(f"{i}. {desc}")
        print("")

        try:
            choice = int(input("请输入序号: "))
            if choice < 1 or choice > len(commands):
                print("输入超出范围\n")
                continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            desc, cmd = commands[choice - 1]

            if cmd == "exit":
                print("退出脚本")
                break

            elif cmd == "pull_logs":
                remote_path = f"/sdcard/Android/data/{PACKAGE_NAME}/files/flog"
                local_path = os.path.join(DOCUMENTS_PATH, f"flog_{timestamp}")
                run_adb_command(f'adb pull "{remote_path}" "{local_path}"', device_id)
                print(f"日志已保存到 {local_path}")

            elif cmd == "logcat":  # 新增 logcat 功能
                logcat_record(device_id)

            elif cmd == "screenshot":
                device_path = "/sdcard/screenshot.png"
                local_path = os.path.join(PICTURES_PATH, f"screenshot_{timestamp}.png")
                
                run_adb_command(f'adb shell screencap -p {device_path}', device_id)
                run_adb_command(f'adb pull {device_path} "{local_path}"', device_id)
                run_adb_command(f'adb shell rm {device_path}', device_id)
                print(f"截图已保存到 {local_path}，设备临时文件已删除")

            elif cmd == "screenrecord":
                device_path = "/sdcard/record.mp4"
                local_path = os.path.join(VIDEOS_PATH, f"record_{timestamp}.mp4")

                print("开始录屏，按回车停止...")
                proc = subprocess.Popen(f'adb -s {device_id} shell screenrecord {device_path}', shell=True)

                input()  # 等待用户回车停止
                run_adb_command('adb shell pkill -INT screenrecord', device_id)
                time.sleep(1)  # 等待文件写入完成

                run_adb_command(f'adb pull {device_path} "{local_path}"', device_id)
                run_adb_command(f'adb shell rm {device_path}', device_id)
                print(f"录屏已保存到 {local_path}，设备临时文件已删除")

            elif cmd == "pull_anr":
                remote_path = "/data/anr/"
                local_path = os.path.join(DOCUMENTS_PATH, f"anr_{timestamp}")
                
                run_adb_command('adb root', device_id)
                run_adb_command(f'adb pull "{remote_path}" "{local_path}"', device_id)
                print(f"ANR 日志目录已保存到 {local_path}")

            else:
                run_adb_command(cmd, device_id)

        except (ValueError, IndexError):
            print("输入有误，请输入有效序号\n")

if __name__ == "__main__":
    main()
