import subprocess
import time

SCREEN_OFF_CMD = (
    "echo suspend > /sys/kernel/debug/dispdbg/command; "
    "echo disp0 > /sys/kernel/debug/dispdbg/name; "
    "echo 1 > /sys/kernel/debug/dispdbg/start"
)

SCREEN_ON_CMD = (
    "echo resume > /sys/kernel/debug/dispdbg/command; "
    "echo disp0 > /sys/kernel/debug/dispdbg/name; "
    "echo 1 > /sys/kernel/debug/dispdbg/start"
)

def adb_shell(cmd):
    subprocess.run(["adb", "shell", cmd], check=False)

while True:
    print("screen off...")
    adb_shell(SCREEN_OFF_CMD)

    time.sleep(2)

    print("screen on...")
    adb_shell(SCREEN_ON_CMD)

    time.sleep(2)