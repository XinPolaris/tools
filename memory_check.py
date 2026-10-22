# -*- coding: utf-8 -*-
import subprocess
from datetime import datetime


ADB = "adb"

KEYWORDS = [
    "FIKS_OS_LINUX",
    "Fotile_HAL_Service",
    "tplayer",
]

PROCESS_TOP_N = 10


def adb_shell(cmd, timeout=10):
    try:
        result = subprocess.run(
            [ADB, "shell", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except FileNotFoundError:
        return "", "adb not found"


def kb_to_mb(kb):
    return kb / 1024.0


def bytes_to_mb(size):
    return size / 1024.0 / 1024.0


def parse_meminfo(text):
    meminfo = {}

    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0].rstrip(":")
            try:
                meminfo[key] = int(parts[1])
            except ValueError:
                pass

    return meminfo


def get_meminfo():
    out, _ = adb_shell("cat /proc/meminfo")
    return parse_meminfo(out)


def get_process_list():
    cmd = r'''
for pid in /proc/[0-9]*; do
    [ -r "$pid/status" ] || continue

    p=${pid##*/}

    name=$(grep '^Name:' "$pid/status" | awk '{print $2}')
    rss=$(grep '^VmRSS:' "$pid/status" | awk '{print $2}')
    vmsize=$(grep '^VmSize:' "$pid/status" | awk '{print $2}')
    vmdata=$(grep '^VmData:' "$pid/status" | awk '{print $2}')
    threads=$(grep '^Threads:' "$pid/status" | awk '{print $2}')

    [ -z "$rss" ] && rss=0
    [ -z "$vmsize" ] && vmsize=0
    [ -z "$vmdata" ] && vmdata=0
    [ -z "$threads" ] && threads=0

    cmdline=$(cat "$pid/cmdline" 2>/dev/null | tr '\0' ' ')
    [ -z "$cmdline" ] && cmdline="$name"

    echo "$rss|$vmsize|$vmdata|$threads|$p|$name|$cmdline"
done
'''
    out, _ = adb_shell(cmd, timeout=20)

    processes = []

    for line in out.splitlines():
        parts = line.split("|", 6)
        if len(parts) != 7:
            continue

        rss, vmsize, vmdata, threads, pid, name, cmdline = parts

        try:
            processes.append({
                "rss": int(rss),
                "vmsize": int(vmsize),
                "vmdata": int(vmdata),
                "threads": int(threads),
                "pid": pid,
                "name": name,
                "cmdline": cmdline,
            })
        except ValueError:
            pass

    processes.sort(key=lambda x: x["rss"], reverse=True)
    return processes


def get_dma_buf_info():
    out, _ = adb_shell("cat /sys/kernel/debug/dma_buf/bufinfo 2>/dev/null", timeout=10)

    info = {
        "ok": False,
        "objects": 0,
        "total_size": 0,
        "ion_size": 0,
        "ve_size": 0,
        "disp_size": 0,
        "unattached_size": 0,
    }

    if not out:
        return info

    info["ok"] = True

    current_size = None
    current_exp = ""
    attached_devices = []
    in_attached = False

    def flush():
        nonlocal current_size, current_exp, attached_devices

        if current_size is None:
            return

        info["objects"] += 1
        info["total_size"] += current_size

        if current_exp == "ion_dma_buf":
            info["ion_size"] += current_size

        if not attached_devices:
            info["unattached_size"] += current_size

        for dev in attached_devices:
            dev_l = dev.lower()

            if "1c0e000" in dev_l or "ve" in dev_l:
                info["ve_size"] += current_size

            if "5000000" in dev_l or "disp" in dev_l:
                info["disp_size"] += current_size

    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue

        if s.startswith("Attached Devices"):
            in_attached = True
            continue

        if s.startswith("Total "):
            in_attached = False
            continue

        parts = s.split()

        # dma-buf object line:
        # size flags mode count exp_name ino
        if len(parts) >= 6:
            try:
                size = int(parts[0])
                exp = parts[4]

                flush()

                current_size = size
                current_exp = exp
                attached_devices = []
                in_attached = False
                continue
            except Exception:
                pass

        if in_attached and current_size is not None:
            attached_devices.append(s)

    flush()

    return info


def check_adb():
    out, err = adb_shell("echo ok", timeout=5)
    if "ok" not in out:
        print("adb 连接异常，请先确认：adb devices / adb shell")
        if err:
            print(err)
        return False
    return True


def print_system(mem, total_rss):
    print("========== System ==========")
    print(
        "MemTotal={:.2f}MB  Free={:.2f}MB  Available={:.2f}MB  Cached={:.2f}MB".format(
            kb_to_mb(mem.get("MemTotal", 0)),
            kb_to_mb(mem.get("MemFree", 0)),
            kb_to_mb(mem.get("MemAvailable", 0)),
            kb_to_mb(mem.get("Cached", 0)),
        )
    )

    print(
        "Slab={:.2f}MB  SUnreclaim={:.2f}MB  Anon={:.2f}MB  Mapped={:.2f}MB".format(
            kb_to_mb(mem.get("Slab", 0)),
            kb_to_mb(mem.get("SUnreclaim", 0)),
            kb_to_mb(mem.get("AnonPages", 0)),
            kb_to_mb(mem.get("Mapped", 0)),
        )
    )

    print(
        "CmaTotal={:.2f}MB  CmaFree={:.2f}MB  ProcessRSS={:.2f}MB".format(
            kb_to_mb(mem.get("CmaTotal", 0)),
            kb_to_mb(mem.get("CmaFree", 0)),
            kb_to_mb(total_rss),
        )
    )
    print()


def print_key_process(processes):
    print("========== Key Process ==========")

    for keyword in KEYWORDS:
        matched = [
            p for p in processes
            if keyword.lower() in p["name"].lower()
            or keyword.lower() in p["cmdline"].lower()
        ]

        if not matched:
            print("{}: not found".format(keyword))
            continue

        for p in matched:
            print(
                "{} PID={} RSS={:.2f}MB VSZ={:.2f}MB DATA={:.2f}MB THR={} CMD={}".format(
                    p["name"],
                    p["pid"],
                    kb_to_mb(p["rss"]),
                    kb_to_mb(p["vmsize"]),
                    kb_to_mb(p["vmdata"]),
                    p["threads"],
                    p["cmdline"][:60]
                )
            )

    print()


def print_process_top(processes):
    print("========== Process Top {} RSS ==========".format(PROCESS_TOP_N))
    print("{:<6} {:>8} {:>8} {:>8} {:>5} {:<18} {}".format(
        "PID", "RSS_MB", "VSZ_MB", "DATA_MB", "THR", "NAME", "CMD"
    ))
    print("-" * 90)

    for p in processes[:PROCESS_TOP_N]:
        print("{:<6} {:>8.2f} {:>8.2f} {:>8.2f} {:>5} {:<18} {}".format(
            p["pid"],
            kb_to_mb(p["rss"]),
            kb_to_mb(p["vmsize"]),
            kb_to_mb(p["vmdata"]),
            p["threads"],
            p["name"][:18],
            p["cmdline"][:45]
        ))

    print()


def print_dma_buf(dma):
    print("========== dma_buf ==========")

    if not dma["ok"]:
        print("dma_buf not available")
        print()
        return

    print(
        "objects={}  total={:.2f}MB  ion={:.2f}MB  VE={:.2f}MB  DISP={:.2f}MB  unattached={:.2f}MB".format(
            dma["objects"],
            bytes_to_mb(dma["total_size"]),
            bytes_to_mb(dma["ion_size"]),
            bytes_to_mb(dma["ve_size"]),
            bytes_to_mb(dma["disp_size"]),
            bytes_to_mb(dma["unattached_size"]),
        )
    )
    print()


def print_diagnose(mem, total_rss, dma):
    print("========== Diagnose ==========")

    mem_avail = mem.get("MemAvailable", 0)
    cma_total = mem.get("CmaTotal", 0)
    cma_free = mem.get("CmaFree", 0)
    sunreclaim = mem.get("SUnreclaim", 0)

    has_warn = False

    if mem_avail < 20 * 1024:
        print("[WARN] MemAvailable < 20MB，可用内存偏低")
        has_warn = True

    if cma_total > 0 and cma_free == 0:
        print("[WARN] CmaFree = 0，视频/显示/DMA buffer 可能有压力")
        has_warn = True

    if sunreclaim > 12 * 1024:
        print("[WARN] SUnreclaim 偏高，内核不可回收内存需要关注")
        has_warn = True

    if total_rss < 60 * 1024 and mem_avail < 25 * 1024:
        print("[INFO] 进程 RSS 不高但可用内存低，优先怀疑内核/驱动/ION/CMA/dma_buf/显示/视频 buffer")
        has_warn = True

    if dma["ok"] and dma["total_size"] > 8 * 1024 * 1024:
        print("[INFO] dma_buf > 8MB，重点观察播放/停止后是否持续增长或不释放")
        has_warn = True

    if not has_warn:
        print("当前没有明显异常")

    print()


def main():
    if not check_adb():
        return

    mem = get_meminfo()
    processes = get_process_list()
    dma = get_dma_buf_info()

    total_rss = sum(p["rss"] for p in processes)

    print("========== ADB MEM CHECK ==========")
    print("Time: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print()

    print_system(mem, total_rss)
    print_key_process(processes)
    print_process_top(processes)
    print_dma_buf(dma)
    print_diagnose(mem, total_rss, dma)


if __name__ == "__main__":
    main()