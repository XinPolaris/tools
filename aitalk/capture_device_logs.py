"""通过 ADB 将多路设备日志持续保存到电脑，保留原始字节并支持断线重连。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import threading
import time


SOURCES = {
    "duiPlus": "/mnt/UDISK/log/app/cache/log/duiPlus.log",
    "MQBus": "/mnt/UDISK/log/app/cache/log/MQBus.log",
    "dds": "/mnt/UDISK/log/app/cache/log/dds.log",
    "auth": "/mnt/UDISK/log/app/cache/log/auth.log",
    "taihangLite": "/mnt/UDISK/log/app/cache/log/taihangLite.log",
    "upload": "/mnt/UDISK/log/app/cache/log/upload.log",
    "fiks": "/tmp/cache/fiks/log.txt",
}


def now_text():
    """统一按北京时间生成采集目录名和元数据时间。"""
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")


def run_adb(adb, *arguments):
    """执行有超时限制的只读 ADB 查询，避免启动阶段一直挂起。"""
    return subprocess.run(
        [adb, *arguments],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def choose_device(adb, requested):
    """仅在设备唯一时自动选择，并始终固定该设备以免重连到其他设备。"""
    result = run_adb(adb, "devices")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Failed to list ADB devices")
    devices = [
        fields[0]
        for line in result.stdout.splitlines()[1:]
        if len(fields := line.split()) >= 2 and fields[1] == "device"
    ]
    if requested:
        if requested not in devices:
            raise RuntimeError(f"Device is unavailable: {requested}")
        return requested
    if len(devices) != 1:
        raise RuntimeError(
            "Connect one authorized ADB device, or select one with --serial. "
            f"Available devices: {', '.join(devices) or 'none'}"
        )
    return devices[0]


def choose_transport(adb, serial):
    """检测可用传输，并识别旧版 ADB 伪终端对换行增加的回车数。"""
    expected = bytes(range(256)) + b"capture-probe\n"
    command = "printf '" + "".join(f"\\{value:03o}" for value in expected) + "'"
    failures = []
    for transport in (("shell", "-T"), ("exec-out",), ("shell",)):
        result = subprocess.run(
            [adb, "-s", serial, *transport, command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            for extra_cr in range(3 if transport == ("shell",) else 1):
                if result.stdout == expected.replace(b"\n", b"\r" * extra_cr + b"\n"):
                    return transport, extra_cr
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        failures.append(f"{' '.join(transport)}: {detail[:200] or 'byte probe failed'}")
    raise RuntimeError("No compatible ADB transport. " + "; ".join(failures))


def choose_tail(adb, serial, interval, transport=("shell", "-T")):
    """检测按文件名持续跟踪的能力，并验证设备接受所选轮询间隔。"""
    for command in ("tail", "busybox tail"):
        result = run_adb(adb, "-s", serial, *transport, f"{command} --help")
        help_text = result.stdout + result.stderr
        if "-F" not in help_text or "-s" not in help_text:
            continue
        result = run_adb(
            adb, "-s", serial, *transport,
            f"{command} -n 0 -s {interval:g} /dev/null",
        )
        # 旧版 shell 不返回远端退出码，还需确认探测命令没有输出错误。
        if result.returncode == 0 and not (result.stdout + result.stderr).strip():
            return command
    raise RuntimeError(
        f"Device tail must support -F and -s with interval={interval:g}. "
        "Use --interval 1 if fractional seconds are unsupported. "
        f"Last probe: {(result.stdout + result.stderr).strip()[:300]}"
    )


def copy_output(pipe, destination, extra_cr, name, stop, errors, mark_reconnect=False):
    """按字节转存数据，还原额外回车，并在重连收到数据时插入分隔线。"""
    pending = b""
    try:
        while chunk := os.read(pipe.fileno(), 65536):
            if mark_reconnect:
                destination.write(b"\n" + b"////////////////////////////\n" * 3)
                mark_reconnect = False
            data = pending + chunk
            if extra_cr:
                # 只保留末尾可能属于换行转换的回车，原文件自带的回车仍完整保留。
                held = min(len(data) - len(data.rstrip(b"\r")), extra_cr)
                pending = data[-held:] if held else b""
                data = data[:-held] if held else data
                data = data.replace(b"\r" * extra_cr + b"\n", b"\n")
            destination.write(data)
        if pending:
            destination.write(pending)
    except Exception as error:
        errors.append(f"{name} output: {error}")
        logging.exception("Output failed: %s", name)
        stop.set()


def make_output_directory(root, serial):
    """每次启动建立独立目录，保留既有采集结果。"""
    root.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", serial) + "_" + now_text()
    index = 1
    while True:
        path = root / (name if index == 1 else f"{name}-{index:02d}")
        try:
            path.mkdir()
            return path
        except FileExistsError:
            index += 1


def follow_source(
    adb, serial, tail, interval, name, remote, output, stop, errors,
    transport=("shell", "-T"), extra_cr=0,
):
    """按设备原文件名采集，重连后重新读取当前文件并追加到同一本地文件。"""
    attempt = 0
    filename = Path(remote).name
    try:
        (output / "diagnostics").mkdir(exist_ok=True)
        while not stop.is_set():
            attempt += 1
            # 使用二进制管道，避免 PowerShell 或文本解码改变日志字节。
            with (output / filename).open("ab", buffering=0) as data_file, (
                output / "diagnostics" / f"{filename}.stderr.txt"
            ).open("ab", buffering=0) as error_file:
                command = (
                    f"exec {tail} -n +1 -F -s {interval:g} {shlex.quote(remote)}"
                )
                process = subprocess.Popen(
                    [adb, "-s", serial, *transport, command],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=error_file,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    ),
                )
                reader = threading.Thread(
                    target=copy_output,
                    args=(
                        process.stdout, data_file, extra_cr, name, stop, errors,
                        attempt > 1 and data_file.tell() > 0,
                    ),
                    name=f"{name}-output",
                )
                reader.start()
                logging.info("Started %s, attempt=%d, source=%s", name, attempt, remote)
                try:
                    while process.poll() is None and not stop.wait(0.2):
                        pass
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                    process.wait()
                    reader.join()
                    process.stdout.close()
                if not stop.is_set():
                    logging.warning(
                        "%s stream ended, exit=%d; retrying in 2 seconds; details=diagnostics/%s.stderr.txt",
                        name, process.returncode, filename,
                    )
            stop.wait(2)
    except Exception as error:
        errors.append(f"{name}: {error}")
        logging.exception("Capture failed: %s", name)
        stop.set()


def main():
    """选择设备、启动多路采集，并在 Ctrl+C 后关闭全部 ADB 子进程。"""
    parser = argparse.ArgumentParser(
        description="Capture voice and FIKS logs to the PC over ADB. Press Ctrl+C to stop."
    )
    parser.add_argument("-s", "--serial", help="ADB device serial")
    parser.add_argument("--adb", default="adb", help="ADB executable path")
    parser.add_argument(
        "--output-root", type=Path, default=Path(__file__).resolve().parent / "captures",
        help="PC output root; each run creates a new subdirectory",
    )
    parser.add_argument(
        "--only", choices=list(SOURCES), nargs="+", help="Capture only selected sources"
    )
    parser.add_argument(
        "--interval", type=float, default=1, help="Device tail polling interval in seconds"
    )
    parser.add_argument(
        "--duration", type=float, help="Stop automatically after this many seconds"
    )
    args = parser.parse_args()
    if not 0.05 <= args.interval <= 10:
        parser.error("--interval must be between 0.05 and 10 seconds")
    if args.duration is not None and args.duration <= 0:
        parser.error("--duration must be greater than zero")
    adb = shutil.which(args.adb)
    if not adb:
        parser.error("ADB executable not found; use --adb with its full path")
    try:
        serial = choose_device(adb, args.serial)
        transport, extra_cr = choose_transport(adb, serial)
        tail = choose_tail(adb, serial, args.interval, transport)
        output = make_output_directory(args.output_root.resolve(), serial)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"[ERROR] {error}")
        return 1

    (output / "diagnostics").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(output / "diagnostics" / "collector.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    selected = {name: SOURCES[name] for name in (args.only or SOURCES)}
    (output / "diagnostics" / "capture.json").write_text(
        json.dumps(
            {
                "serial": serial,
                "started_beijing": now_text(),
                "tail": tail,
                "transport": list(transport),
                "inserted_cr_per_lf": extra_cr,
                "interval_seconds": args.interval,
                "sources": selected,
                "reconnect_policy": "Append to same file with three slash separator lines; reread current file; overlap is possible",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    logging.info("Device: %s; output: %s", serial, output)
    logging.info("Transport: %s; inserted CR per LF: %d", " ".join(transport), extra_cr)
    logging.info("Capturing %d sources. Press Ctrl+C to stop.", len(selected))
    stop = threading.Event()
    errors = []
    threads = [
        threading.Thread(
            target=follow_source,
            args=(
                adb, serial, tail, args.interval, name, remote, output, stop, errors,
                transport, extra_cr,
            ),
            name=name,
        )
        for name, remote in selected.items()
    ]
    started = time.monotonic()
    next_status = started + 30
    try:
        for thread in threads:
            thread.start()
        while not stop.wait(0.2):
            elapsed = time.monotonic() - started
            if args.duration is not None and elapsed >= args.duration:
                break
            if time.monotonic() >= next_status:
                total = 0
                for remote in selected.values():
                    path = output / Path(remote).name
                    if path.exists():
                        total += path.stat().st_size
                logging.info("Capture running: %.0f seconds, %.2f MiB saved", elapsed, total / 1048576)
                next_status = time.monotonic() + 30
    except KeyboardInterrupt:
        logging.info("Stop requested")
    finally:
        stop.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join()
        logging.info("Capture stopped. Output: %s", output)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
