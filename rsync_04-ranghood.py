#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys

# ================= 配置区 =================

# 注意：这里不能写 D:\project\04-ranghood
# rsync 会把 D: 当成远程地址
# MobaXterm 环境一般用 /drives/d/...
LOCAL_PATH = "/drives/d/project/04-ranghood"

REMOTE_USER = "huangx"
REMOTE_HOST = "10.49.3.18"
REMOTE_PATH = "/home/huangx/project/04-ranghood"

# 只同步这两个目录
SYNC_DIRS = [
    "project_app/linux_common",
    "project_app/linux_app_fotile/project/04_hood"
]

# 强制走密码登录，不读取 C:\Users\huangxina\.ssh\id_rsa
SSH_CMD = (
    "ssh "
    "-o PubkeyAuthentication=no "
    "-o PreferredAuthentications=password "
    "-o StrictHostKeyChecking=no "
    "-o UserKnownHostsFile=/dev/null"
)

# ================= 逻辑区 =================

def build_rsync_cmd(subdir: str):
    local_dir = f"{LOCAL_PATH}/{subdir}/"
    remote_dir = f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_PATH}/{subdir}/"

    cmd = [
        "rsync",
        "-avz",
        "--delete",
        "-e",
        SSH_CMD,
        local_dir,
        remote_dir
    ]

    return cmd, local_dir, remote_dir


def run_sync():
    for subdir in SYNC_DIRS:
        cmd, local_dir, remote_dir = build_rsync_cmd(subdir)

        print("\n========================================")
        print(f"同步目录: {subdir}")
        print(f"本地: {local_dir}")
        print(f"远程: {remote_dir}")
        print("========================================")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            print(f"\n同步失败: {subdir}")
            print(f"错误码: {result.returncode}")
            sys.exit(result.returncode)

    print("\n所有目录同步完成")


if __name__ == "__main__":
    run_sync()