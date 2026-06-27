import subprocess
import os

# ---------- 配置 ----------
LOCAL_DIR = r"D:\project_linux\04-ranghood-2\project_app\linux_app_fotile\project\04_hood\res"
REMOTE_DIR = "/mnt/app"
ADB_CMD = "adb"  # 如果 adb 不在 PATH，可写 adb.exe 全路径
# -------------------------

def push_res_content(local_dir, remote_dir):
    # 1. 先删除远程目录下所有内容，但保留 /mnt/app 本身
    print(f"清空远程目录内容: {remote_dir}/*")
    try:
        subprocess.run([ADB_CMD, "shell", "rm", "-rf", f"{remote_dir}/*"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"清空远程目录失败: {e}")

    # 2. 遍历 res 下的所有文件和文件夹
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        try:
            subprocess.run([ADB_CMD, "push", local_path, remote_path], check=True)
            print(f"已推送: {local_path} -> {remote_path}")
        except subprocess.CalledProcessError as e:
            print(f"推送失败: {local_path} -> {remote_path}, 错误: {e}")

if __name__ == "__main__":
    push_res_content(LOCAL_DIR, REMOTE_DIR)
    print("全部文件推送完成！")