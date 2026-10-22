#!/usr/bin/env python3
"""通过 ADB 将设备端 arecord 的原始音频流实时保存为电脑端 WAV 文件。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import queue
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=(
            "Stream raw PCM from device arecord through ADB and create a WAV file "
            "on this computer."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Output WAV base path; the segment start time is appended to its name."
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Recording duration in seconds; 0 records until Ctrl+C (default: 0).",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Sample rate in Hz (default: 16000).",
    )
    parser.add_argument(
        "--channels", type=int, default=8, help="Channel count (default: 8)."
    )
    parser.add_argument(
        "--pcm-device",
        default="default",
        help="ALSA PCM capture device (default: default).",
    )
    parser.add_argument("--serial", help="ADB device serial when multiple devices exist.")
    parser.add_argument(
        "--adb", default="adb", help="ADB executable or path (default: adb)."
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output file."
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=5.0,
        help="Flush audio data and refresh the WAV header every N seconds (default: 5).",
    )
    return parser


class DurableWavWriter:
    """实时写入并周期性固化 WAV 文件头和音频数据。"""

    def __init__(
        self,
        path: Path,
        channels: int,
        sample_rate: int,
        overwrite: bool,
    ) -> None:
        self._file = path.open("wb" if overwrite else "xb")
        self._data_bytes = 0
        self._synced_data_bytes = 0
        self._closed = False
        self._file.write(
            struct.pack(
                "<4sI4s4sIHHIIHH4sI",
                b"RIFF",
                36,
                b"WAVE",
                b"fmt ",
                16,
                1,
                channels,
                sample_rate,
                sample_rate * channels * 2,
                channels * 2,
                16,
                b"data",
                0,
            )
        )
        self._file.flush()
        os.fsync(self._file.fileno())

    def __enter__(self) -> DurableWavWriter:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: object,
    ) -> None:
        self.close()

    def writeframesraw(self, data: bytes) -> None:
        """追加完整 PCM 帧，但暂不改写 WAV 文件头。"""
        self._file.write(data)
        self._data_bytes += len(data)

    def sync(self) -> None:
        """先固化音频数据，再更新并固化 WAV 长度字段。"""
        if self._closed or self._data_bytes == self._synced_data_bytes:
            return

        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.seek(4)
        self._file.write(struct.pack("<I", 36 + self._data_bytes))
        self._file.seek(40)
        self._file.write(struct.pack("<I", self._data_bytes))
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.seek(0, os.SEEK_END)
        self._synced_data_bytes = self._data_bytes

    def close(self) -> None:
        """完成最后一次固化并关闭文件。"""
        if self._closed:
            return
        try:
            self.sync()
        finally:
            self._closed = True
            self._file.close()


def subprocess_flags() -> int:
    """在 Windows 上避免子进程直接收到当前控制台的 Ctrl+C。"""
    if os.name == "nt":
        return subprocess.CREATE_NO_WINDOW
    return 0


def resolve_adb(adb_argument: str) -> str:
    """解析并校验 ADB 可执行文件。"""
    adb_path = shutil.which(adb_argument)
    if adb_path:
        return adb_path

    candidate = Path(adb_argument).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())

    raise RuntimeError(f"ADB executable not found: {adb_argument}")


def select_device(adb_path: str, requested_serial: str | None) -> str:
    """选择唯一可用的 ADB 设备。"""
    result = subprocess.run(
        [adb_path, "devices"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=subprocess_flags(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to list ADB devices.")

    devices: dict[str, str] = {}
    for line in result.stdout.splitlines()[1:]:
        fields = line.strip().split()
        if len(fields) >= 2:
            devices[fields[0]] = fields[1]

    if requested_serial:
        state = devices.get(requested_serial)
        if state != "device":
            raise RuntimeError(
                f"ADB device {requested_serial!r} is not ready (state: {state or 'missing'})."
            )
        return requested_serial

    ready_devices = [serial for serial, state in devices.items() if state == "device"]
    if not ready_devices:
        states = ", ".join(f"{serial}={state}" for serial, state in devices.items())
        raise RuntimeError(
            "No ready ADB device found." + (f" Detected: {states}" if states else "")
        )
    if len(ready_devices) > 1:
        raise RuntimeError(
            "Multiple ADB devices found; select one with --serial: "
            + ", ".join(ready_devices)
        )
    return ready_devices[0]


def find_remote_command(adb_prefix: list[str], command: str) -> str:
    """查找设备端命令的绝对路径。"""
    result = subprocess.run(
        [*adb_prefix, "shell", f"command -v {shlex.quote(command)}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=subprocess_flags(),
        check=False,
    )
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not paths:
        raise RuntimeError(
            result.stderr.strip() or f"{command} was not found on the device."
        )
    return paths[-1]


def resolve_output(
    output_argument: Path | None, segment_started_at: float, overwrite: bool
) -> Path:
    """根据当前分段的开始时间生成并校验电脑端输出路径。"""
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(segment_started_at))
    if output_argument is None:
        output_path = (
            Path(__file__).resolve().parent
            / "recordings"
            / f"output_{timestamp}.wav"
        )
    else:
        base_path = output_argument.expanduser().resolve()
        output_path = base_path.with_name(
            f"{base_path.stem}_{timestamp}{base_path.suffix or '.wav'}"
        )

    if output_path.exists() and not overwrite:
        raise RuntimeError(f"Output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def report_saved_segment(
    output_path: Path, data_bytes: int, sample_rate: int, frame_size: int
) -> None:
    """输出已完成录音分段的路径、时长和大小。"""
    print(
        f"Saved   : {output_path}\n"
        f"Duration: {data_bytes / (sample_rate * frame_size):.3f}s\n"
        f"Size    : {data_bytes + 44} bytes"
    )


def read_stdout(stream: object, chunks: queue.Queue[bytes | None]) -> None:
    """持续读取二进制音频流，避免 ADB 管道被填满。"""
    try:
        while True:
            data = stream.read(64 * 1024)  # type: ignore[attr-defined]
            if not data:
                break
            chunks.put(data)
    finally:
        chunks.put(None)


def read_stderr(stream: object, captured: bytearray) -> None:
    """收集 arecord 和 ADB 的错误输出。"""
    while True:
        data = stream.read(4096)  # type: ignore[attr-defined]
        if not data:
            return
        captured.extend(data)


def stop_remote_arecord(adb_prefix: list[str], pid_file: str) -> bool:
    """仅停止 PID 文件对应且仍为 arecord 的设备端进程。"""
    quoted_pid_file = shlex.quote(pid_file)
    command = (
        f"pid=$(cat {quoted_pid_file} 2>/dev/null) || exit 1; "
        'case "$pid" in ""|*[!0-9]*) exit 2;; esac; '
        '[ "$(cat /proc/$pid/comm 2>/dev/null)" = "arecord" ] || exit 3; '
        'kill -INT "$pid"'
    )
    try:
        result = subprocess.run(
            [*adb_prefix, "shell", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            creationflags=subprocess_flags(),
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def read_remote_text(adb_prefix: list[str], remote_path: str) -> str:
    """读取设备端的小型文本诊断文件。"""
    try:
        result = subprocess.run(
            [*adb_prefix, "shell", "cat", remote_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=subprocess_flags(),
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def remove_remote_files(adb_prefix: list[str], remote_paths: list[str]) -> None:
    """清理本脚本创建的设备端临时控制文件。"""
    try:
        subprocess.run(
            [*adb_prefix, "shell", "rm", "-f", *remote_paths],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            creationflags=subprocess_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def start_stream(
    adb_prefix: list[str],
    arecord_path: str,
    hexdump_path: str,
    mkfifo_path: str,
    pid_file: str,
    fifo_file: str,
    error_file: str,
    pcm_device: str,
    sample_rate: int,
    channels: int,
) -> subprocess.Popen[bytes]:
    """启动设备端采集并通过 ADB 标准输出传输原始 PCM。"""
    remote_script = (
        f"rm -f {shlex.quote(fifo_file)} {shlex.quote(error_file)}; "
        f"{shlex.quote(mkfifo_path)} {shlex.quote(fifo_file)} || exit 10; "
        f"{shlex.quote(arecord_path)} -q -D {shlex.quote(pcm_device)} "
        f"-t raw -f S16_LE -r {sample_rate} -c {channels} "
        f"> {shlex.quote(fifo_file)} 2> {shlex.quote(error_file)} & "
        "recorder_pid=$!; "
        f"echo \"$recorder_pid\" > {shlex.quote(pid_file)}; "
        f"{shlex.quote(hexdump_path)} -v "
        f"-e {shlex.quote('1/1 \"%02x\"')} < {shlex.quote(fifo_file)}; "
        "encoder_status=$?; "
        'kill -INT "$recorder_pid" 2>/dev/null; '
        'wait "$recorder_pid" 2>/dev/null; '
        f"rm -f {shlex.quote(fifo_file)}; "
        'exit "$encoder_status"'
    )
    process = subprocess.Popen(
        [*adb_prefix, "shell", remote_script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        creationflags=subprocess_flags(),
    )
    return process


def record(args: argparse.Namespace, stop_event: threading.Event) -> int:
    """执行录音、停止和电脑端 WAV 封装流程。"""
    if not 0 <= args.duration < float("inf"):
        raise RuntimeError("--duration cannot be negative.")
    if args.sample_rate <= 0:
        raise RuntimeError("--sample-rate must be positive.")
    if not 1 <= args.channels <= 32:
        raise RuntimeError("--channels must be between 1 and 32.")
    if not 0 < args.sync_interval < float("inf"):
        raise RuntimeError("--sync-interval must be positive.")
    frame_size = args.channels * 2
    segment_duration_seconds = 30 * 60
    if (
        round((segment_duration_seconds + args.sync_interval) * args.sample_rate)
        * frame_size
        > 0xFFFFFFFF - 36
    ):
        raise RuntimeError("A 30-minute segment exceeds the WAV size limit.")

    adb_path = resolve_adb(args.adb)
    serial = select_device(adb_path, args.serial)
    adb_prefix = [adb_path, "-s", serial]
    arecord_path = find_remote_command(adb_prefix, "arecord")
    hexdump_path = find_remote_command(adb_prefix, "hexdump")
    mkfifo_path = find_remote_command(adb_prefix, "mkfifo")
    remote_token = f"record_to_pc_{os.getpid()}_{int(time.time())}"
    pid_file = f"/tmp/{remote_token}.pid"
    fifo_file = f"/tmp/{remote_token}.fifo"
    error_file = f"/tmp/{remote_token}.err"

    process = start_stream(
        adb_prefix,
        arecord_path,
        hexdump_path,
        mkfifo_path,
        pid_file,
        fifo_file,
        error_file,
        args.pcm_device,
        args.sample_rate,
        args.channels,
    )
    if process.stdout is None or process.stderr is None:
        process.terminate()
        raise RuntimeError("Failed to open ADB output pipes.")

    chunks: queue.Queue[bytes | None] = queue.Queue()
    stderr_data = bytearray()
    stdout_thread = threading.Thread(
        target=read_stdout, args=(process.stdout, chunks), daemon=True
    )
    stderr_thread = threading.Thread(
        target=read_stderr, args=(process.stderr, stderr_data), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    print(f"Device : {serial}")
    print(f"Format : S16_LE, {args.sample_rate} Hz, {args.channels} channels")
    print("Segment: 30 minutes per WAV file")
    print("Recording... Press Ctrl+C to stop.")

    target_data_bytes: int | None = None
    if args.duration:
        target_data_bytes = (
            max(1, round(args.duration * args.sample_rate)) * frame_size
        )
    bytes_written = 0
    segment_bytes_written = 0
    segments_saved = 0
    remainder = b""
    hex_remainder = b""
    started_at = time.monotonic()
    segment_started_at = started_at
    last_progress_at = started_at
    last_sync_at = started_at
    stop_sent_at: float | None = None
    stream_ended = False
    recording_error: str | None = None
    wav_file: DurableWavWriter | None = None
    output_path: Path | None = None

    try:
        output_path = resolve_output(args.output, time.time(), args.overwrite)
        wav_file = DurableWavWriter(
            output_path, args.channels, args.sample_rate, args.overwrite
        )
        print(f"Output : {output_path}")

        while not stream_ended:
            now = time.monotonic()
            if target_data_bytes is not None and bytes_written >= target_data_bytes:
                stop_event.set()

            if stop_event.is_set() and stop_sent_at is None:
                print("\nStopping remote recorder...")
                stop_sent_at = now
                if not stop_remote_arecord(adb_prefix, pid_file):
                    print("Warning: remote stop was not confirmed; closing ADB stream.")
                    process.terminate()

            if (
                stop_sent_at is not None
                and now - stop_sent_at >= 5
                and process.poll() is None
            ):
                print("Warning: recorder did not exit in time; closing ADB stream.")
                process.terminate()

            try:
                data = chunks.get(timeout=0.25)
            except queue.Empty:
                continue

            if data is None:
                stream_ended = True
                continue

            encoded_data = hex_remainder + b"".join(data.split())
            encoded_length = len(encoded_data) - len(encoded_data) % 2
            try:
                decoded_data = bytes.fromhex(
                    encoded_data[:encoded_length].decode("ascii")
                )
            except (UnicodeDecodeError, ValueError) as exc:
                recording_error = f"Invalid encoded audio stream: {exc}"
                stop_event.set()
                process.terminate()
                stream_ended = True
                continue
            hex_remainder = encoded_data[encoded_length:]

            complete_data = remainder + decoded_data
            complete_length = len(complete_data) - len(complete_data) % frame_size
            writable_length = complete_length
            if target_data_bytes is not None:
                writable_length = min(
                    writable_length, target_data_bytes - bytes_written
                )
            writable_length -= writable_length % frame_size
            if writable_length:
                wav_file.writeframesraw(complete_data[:writable_length])
                bytes_written += writable_length
                segment_bytes_written += writable_length
            remainder = complete_data[complete_length:]

            now = time.monotonic()
            if now - last_sync_at >= args.sync_interval:
                wav_file.sync()
                last_sync_at = now
                recording_continues = not stop_event.is_set() and (
                    target_data_bytes is None or bytes_written < target_data_bytes
                )
                if (
                    now - segment_started_at >= segment_duration_seconds
                    and recording_continues
                ):
                    wav_file.close()
                    wav_file = None
                    report_saved_segment(
                        output_path,
                        segment_bytes_written,
                        args.sample_rate,
                        frame_size,
                    )
                    segments_saved += 1
                    segment_bytes_written = 0
                    segment_started_at = now
                    output_path = resolve_output(
                        args.output, time.time(), args.overwrite
                    )
                    wav_file = DurableWavWriter(
                        output_path,
                        args.channels,
                        args.sample_rate,
                        args.overwrite,
                    )
                    print(f"Output : {output_path}")
            if now - last_progress_at >= 5:
                recorded_seconds = bytes_written / (args.sample_rate * frame_size)
                print(
                    f"Recorded {recorded_seconds:.1f}s, "
                    f"{bytes_written / (1024 * 1024):.1f} MiB"
                )
                last_progress_at = now
    except OSError as exc:
        recording_error = f"Failed to write WAV data: {exc}"
        stop_event.set()
    finally:
        if wav_file is not None:
            try:
                wav_file.close()
                if segment_bytes_written and output_path is not None:
                    report_saved_segment(
                        output_path,
                        segment_bytes_written,
                        args.sample_rate,
                        frame_size,
                    )
                    segments_saved += 1
                elif output_path is not None:
                    output_path.unlink(missing_ok=True)
            except OSError as exc:
                if recording_error is None:
                    recording_error = f"Failed to finalize WAV data: {exc}"
        if process.poll() is None:
            stop_remote_arecord(adb_prefix, pid_file)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        remote_error = read_remote_text(adb_prefix, error_file)
        remove_remote_files(adb_prefix, [pid_file, fifo_file, error_file])

    stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
    if bytes_written == 0:
        detail = (
            remote_error
            or stderr_text
            or recording_error
            or "The audio stream ended without data."
        )
        raise RuntimeError(detail)

    recorded_seconds = bytes_written / (args.sample_rate * frame_size)
    print(
        f"Finished: {segments_saved} WAV file(s)\n"
        f"Total duration: {recorded_seconds:.3f}s"
    )

    if recording_error:
        print(f"Warning: {recording_error}", file=sys.stderr)
        return 1
    if hex_remainder:
        print("Warning: encoded audio stream ended mid-byte.", file=sys.stderr)
        return 1
    if remote_error:
        print(f"Warning: {remote_error}", file=sys.stderr)
        return 1
    if process.returncode not in (0, None) and not stop_event.is_set():
        print(
            f"Warning: ADB stream exited with code {process.returncode}."
            + (f"\n{stderr_text}" if stderr_text else ""),
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    """解析参数并安装安全停止处理。"""
    args = build_parser().parse_args()
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        """收到退出信号后请求录音主循环安全收尾。"""
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    try:
        return record(args, stop_event)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
