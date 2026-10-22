#!/usr/bin/env bash
# 在电脑端通过 ADB 录制设备音频，适用于 Windows Git Bash 和 GNU/Linux。
# 使用 Git Bash 自带的工具完成 PCM 解码和 WAV 封装，不依赖 Python。

set -u
set -o pipefail

usage() {
    cat <<'EOF'
Usage: bash record_to_pc.sh [OPTIONS]

Stream device arecord audio through ADB into timestamped WAV files.
Each WAV contains at most 30 minutes of audio.

  --output PATH        Output WAV base path (default: recordings/output.wav
                       beside this script); a start timestamp is appended.
  --duration SECONDS   Total audio duration; 0 records until Ctrl+C (default: 0).
  --sample-rate HZ     Sample rate (default: 16000).
  --channels COUNT     Channel count, 1..32 (default: 8).
  --pcm-device NAME    Device ALSA capture PCM (default: default).
  --serial SERIAL      Select an ADB device when multiple devices are ready.
  --adb PATH           ADB executable or path (default: adb).
  --overwrite          Replace an existing output file.
  --sync-interval SEC  Refresh and flush the WAV header (default: 5).
  -h, --help           Show this help.

Examples in Git Bash:
  bash /d/tools/record_to_pc.sh --duration 60
  bash /d/tools/record_to_pc.sh --output /d/audio/test.wav --channels 8
  bash /d/tools/record_to_pc.sh --serial DEVICE_SERIAL --duration 10
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

local_path() {
    # 先转换电脑端路径，再禁止 ADB 参数中的设备路径被 MSYS 自动转换。
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -u -- "$1"
    else
        printf '%s\n' "$1"
    fi
}

remote_quote() {
    # 设备端使用 POSIX Shell 单引号规则，避免 PCM 名称中的字符被执行。
    printf "'%s'" "${1//\'/\'\\\'\'}"
}

adb_control() {
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' \
        timeout 10 "$adb_path" -s "$serial" shell "$1"
}

find_remote_command() {
    local result
    result=$(adb_control "command -v $(remote_quote "$1")") || return 1
    result=${result//$'\r'/}
    result=${result##*$'\n'}
    [[ $result == /* ]] || return 1
    printf '%s\n' "$result"
}

write_le16() {
    local escaped
    printf -v escaped '\\%03o\\%03o' "$(($1 & 255))" "$(($1 >> 8 & 255))"
    printf '%b' "$escaped"
}

write_le32() {
    local escaped
    printf -v escaped '\\%03o\\%03o\\%03o\\%03o' \
        "$(($1 & 255))" "$(($1 >> 8 & 255))" \
        "$(($1 >> 16 & 255))" "$(($1 >> 24 & 255))"
    printf '%b' "$escaped"
}

write_header() {
    printf RIFF
    write_le32 "$(($1 + 36))"
    printf 'WAVEfmt '
    write_le32 16
    write_le16 1
    write_le16 "$channels"
    write_le32 "$sample_rate"
    write_le32 "$byte_rate"
    write_le16 "$frame_size"
    write_le16 16
    printf data
    write_le32 "$1"
}

refresh_header() {
    local size data_bytes
    size=$(stat -c %s -- "$output_path") || return 1
    ((size >= 44)) || return 1
    data_bytes=$(((size - 44) / frame_size * frame_size))
    ((data_bytes != synced_data_bytes)) || return 0
    # dd 使用追加模式写音频，更新文件头不会影响它的写入位置。
    # MSYS 的 sync 以只读方式打开文件会导致刷盘失败，改用可写描述符执行 fsync。
    dd if=/dev/null of="$output_path" count=0 conv=notrunc,fsync status=none || return 1
    write_header "$data_bytes" | dd of="$output_path" bs=44 count=1 \
        iflag=fullblock conv=notrunc,fsync status=none || return 1
    synced_data_bytes=$data_bytes
}

open_segment() {
    local timestamp timestamp_suffix=
    timestamp=$(date +%Y%m%d_%H%M%S) || return 1
    # 设备数据快速回放或系统时间调整时，同一秒内的新分段也使用独立文件名。
    if [[ $timestamp == "$last_segment_timestamp" ]]; then
        timestamp_sequence=$((timestamp_sequence + 1))
        printf -v timestamp_suffix '_%03d' "$timestamp_sequence"
    else
        timestamp_sequence=1
    fi
    last_segment_timestamp=$timestamp
    output_path="$output_dir/${output_stem}_${timestamp}${timestamp_suffix}${output_suffix}"
    output_created=0
    if ((overwrite)); then
        : > "$output_path" || return 1
    else
        (set -o noclobber; : > "$output_path") 2>/dev/null || {
            printf 'Error: Cannot create output (it may already exist): %s\n' "$output_path" >&2
            return 1
        }
    fi
    output_created=1
    write_header 0 > "$output_path" || return 1
    synced_data_bytes=-1
    refresh_header || return 1
    printf 'Output : %s\n' "$output_path"
}

save_segment() {
    local size data_bytes
    ((output_created)) || return 0
    size=$(stat -c %s -- "$output_path") || return 1
    ((size >= 44)) || return 1
    data_bytes=$(((size - 44) / frame_size * frame_size))
    # 流中断时丢弃末尾不完整的 PCM 帧，保证播放器可以正确读取。
    truncate -s "$((data_bytes + 44))" -- "$output_path" || return 1
    refresh_header || return 1
    if ((data_bytes)); then
        printf 'Saved   : %s\n' "$output_path"
        awk -v bytes="$data_bytes" -v rate="$byte_rate" \
            'BEGIN { printf "Duration: %.3fs\nSize    : %.0f bytes\n", bytes/rate, bytes+44 }'
        total_bytes=$((total_bytes + data_bytes))
        segments_saved=$((segments_saved + 1))
    else
        rm -f -- "$output_path" || return 1
    fi
    output_created=0
}

request_stop() {
    stop_requested=1
}

stop_remote() {
    ((stream_started && !stop_sent)) || return 0
    stop_sent=1
    stop_started=$SECONDS
    printf '\nStopping remote recorder...\n'
    # 只停止本次 PID 文件指向的 arecord，不影响其他录音进程。
    if ! MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' timeout 5 \
        "$adb_path" -s "$serial" shell \
        "pid=\$(cat $(remote_quote "$pid_file") 2>/dev/null) || exit 1;
         case \"\$pid\" in ''|*[!0-9]*) exit 2;; esac;
         [ \"\$(cat /proc/\$pid/comm 2>/dev/null)\" = arecord ] || exit 3;
         kill -INT \"\$pid\"" >/dev/null 2>&1; then
        printf 'Warning: Remote stop was not confirmed; closing ADB stream.\n' >&2
        kill -TERM "$adb_pid" 2>/dev/null || :
    fi
}

cleanup() {
    local exit_status=$? pid deadline
    trap - EXIT
    trap '' INT TERM
    if [[ -n $adb_pid ]] && kill -0 "$adb_pid" 2>/dev/null; then
        stop_remote
    fi
    # 关闭读取端使解码器退出，再限时回收本次启动的子进程。
    if [[ -n $audio_fd ]]; then
        exec {audio_fd}<&-
    fi
    for pid in "$writer_pid" "$decoder_pid" "$adb_pid"; do
        [[ -n $pid ]] || continue
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || :
            deadline=$((SECONDS + 2))
            while kill -0 "$pid" 2>/dev/null && ((SECONDS < deadline)); do
                sleep 0.1
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -KILL "$pid" 2>/dev/null || :
            fi
        fi
        wait "$pid" 2>/dev/null || :
    done
    if ((output_created)); then
        save_segment || {
            printf 'Error: Failed to finalize WAV: %s\n' "$output_path" >&2
            exit_status=1
        }
    fi
    if ((stream_started)); then
        adb_control "rm -f $(remote_quote "$pid_file") $(remote_quote "$fifo_file") $(remote_quote "$error_file")" \
            >/dev/null 2>&1 || :
    fi
    rm -f -- "$work_dir/encoded" "$work_dir/audio" "$work_dir/adb.err" \
        "$work_dir/decode.err" "$work_dir/write.err"
    rmdir -- "$work_dir" 2>/dev/null || :
    exit "$exit_status"
}

output_argument=
duration=0
sample_rate=16000
channels=8
pcm_device=default
serial=
adb_argument=adb
overwrite=0
sync_interval=5

while (($#)); do
    case $1 in
        --*=*) set -- "${1%%=*}" "${1#*=}" "${@:2}"; continue ;;
        -h|--help) usage; exit 0 ;;
        --overwrite) overwrite=1; shift; continue ;;
        --output|--duration|--sample-rate|--channels|--pcm-device|--serial|--adb|--sync-interval)
            (($# >= 2)) || fail "Missing value for $1"
            [[ -n $2 ]] || fail "Empty value for $1"
            case $1 in
                --output) output_argument=$2 ;;
                --duration) duration=$2 ;;
                --sample-rate) sample_rate=$2 ;;
                --channels) channels=$2 ;;
                --pcm-device) pcm_device=$2 ;;
                --serial) serial=$2 ;;
                --adb) adb_argument=$2 ;;
                --sync-interval) sync_interval=$2 ;;
            esac
            shift 2 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

for tool in awk cat date dd dirname basename mkdir mkfifo mktemp rm rmdir sleep stat timeout truncate xxd; do
    command -v "$tool" >/dev/null 2>&1 || fail "Required command not found: $tool"
done
[[ $sample_rate =~ ^[0-9]{1,10}$ ]] || fail '--sample-rate must be a positive integer.'
[[ $channels =~ ^[0-9]{1,2}$ ]] || fail '--channels must be between 1 and 32.'
sample_rate=$((10#$sample_rate))
channels=$((10#$channels))
((sample_rate > 0 && sample_rate <= 2147483647)) || fail '--sample-rate is out of range.'
((channels >= 1 && channels <= 32)) || fail '--channels must be between 1 and 32.'
frame_size=$((channels * 2))
byte_rate=$((sample_rate * frame_size))
segment_limit=$((byte_rate * 1800))
((segment_limit <= 4294967259)) || fail 'A 30-minute segment exceeds the WAV size limit.'
number_pattern='^[+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$'
[[ $duration =~ $number_pattern ]] || fail '--duration must be a nonnegative finite number.'
[[ $sync_interval =~ $number_pattern ]] || fail '--sync-interval must be positive and finite.'
target_bytes=$(awk -v value="$duration" -v rate="$sample_rate" -v frame="$frame_size" \
    'BEGIN { n=int(value*rate+0.5); if (value>0 && n<1) n=1;
             if (n*frame>9007199254740991 || n<0) exit 1; printf "%.0f", n*frame }') \
    || fail '--duration is too large.'
sync_ms=$(awk -v value="$sync_interval" \
    'BEGIN { if (!(value>0) || value>9007199254740) exit 1;
             n=int(value*1000); printf "%.0f", n<1 ? 1 : n }') \
    || fail '--sync-interval is out of range.'

adb_path=$(command -v "$adb_argument" 2>/dev/null) || adb_path=$(local_path "$adb_argument")
[[ -f $adb_path && -x $adb_path ]] || fail "ADB executable not found: $adb_argument"
devices=$(MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' timeout 10 "$adb_path" devices) \
    || fail 'Failed to list ADB devices.'
ready_devices=()
requested_state=missing
while read -r device state rest; do
    state=${state//$'\r'/}
    [[ $device != 'List' && -n $device ]] || continue
    [[ $device != "$serial" ]] || requested_state=$state
    [[ $state != device ]] || ready_devices+=("$device")
done <<< "$devices"
if [[ -n $serial ]]; then
    [[ $requested_state == device ]] || fail "ADB device $serial is not ready (state: $requested_state)."
else
    ((${#ready_devices[@]})) || fail 'No ready ADB device found.'
    ((${#ready_devices[@]} == 1)) || fail "Multiple ADB devices found; use --serial: ${ready_devices[*]}"
    serial=${ready_devices[0]}
fi
arecord_path=$(find_remote_command arecord) || fail 'arecord was not found on the device.'
hexdump_path=$(find_remote_command hexdump) || fail 'hexdump was not found on the device.'
mkfifo_path=$(find_remote_command mkfifo) || fail 'mkfifo was not found on the device.'

if [[ -n $output_argument ]]; then
    output_argument=$(local_path "$output_argument") || fail 'Invalid output path.'
else
    output_argument="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/recordings/output.wav"
fi
output_dir=$(dirname -- "$output_argument")
mkdir -p -- "$output_dir" || fail "Cannot create output directory: $output_dir"
output_dir=$(cd -- "$output_dir" && pwd -P) || fail 'Cannot resolve output directory.'
output_stem=$(basename -- "$output_argument")
output_suffix=.wav
if [[ $output_stem == ?*.* ]]; then
    output_suffix=.${output_stem##*.}
    output_stem=${output_stem%.*}
fi

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/record_to_pc.XXXXXXXX") || fail 'Cannot create temporary directory.'
remote_token="record_to_pc_$$_$(date +%s)_$RANDOM"
pid_file=/tmp/$remote_token.pid
fifo_file=/tmp/$remote_token.fifo
error_file=/tmp/$remote_token.err
stream_started=0
stop_requested=0
stop_sent=0
stop_started=0
adb_pid=
decoder_pid=
writer_pid=
audio_fd=
output_path=
output_created=0
synced_data_bytes=-1
total_bytes=0
segments_saved=0
last_segment_timestamp=
timestamp_sequence=0
trap request_stop INT TERM
trap cleanup EXIT
mkfifo "$work_dir/encoded" "$work_dir/audio" || fail 'Cannot create local audio pipes.'
open_segment || fail 'Cannot initialize output WAV.'

# 十六进制传输避免部分 ADB Shell 在 Windows 下改写原始 PCM 中的换行字节。
remote_script="umask 077;
$(remote_quote "$mkfifo_path") $(remote_quote "$fifo_file") || exit 10;
$(remote_quote "$arecord_path") -q -D $(remote_quote "$pcm_device") \
-t raw -f S16_LE -r $sample_rate -c $channels \
> $(remote_quote "$fifo_file") 2> $(remote_quote "$error_file") &
recorder_pid=\$!;
echo \"\$recorder_pid\" > $(remote_quote "$pid_file");
trap 'kill -INT \"\$recorder_pid\" 2>/dev/null;
      wait \"\$recorder_pid\" 2>/dev/null;
      rm -f $(remote_quote "$fifo_file")' EXIT;
$(remote_quote "$hexdump_path") -v -e $(remote_quote '1/1 "%02x"') < $(remote_quote "$fifo_file")"

xxd -r -p < "$work_dir/encoded" > "$work_dir/audio" 2> "$work_dir/decode.err" &
decoder_pid=$!
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' "$adb_path" -s "$serial" shell "$remote_script" \
    < /dev/null > "$work_dir/encoded" 2> "$work_dir/adb.err" &
adb_pid=$!
stream_started=1
exec {audio_fd}< "$work_dir/audio"
printf 'Device : %s\nFormat : S16_LE, %s Hz, %s channels\n' "$serial" "$sample_rate" "$channels"
printf 'Segment: 30 minutes per WAV file\nRecording... Press Ctrl+C to stop.\n'
last_sync_ms=$(date +%s%3N)
last_progress=$SECONDS

while :; do
    segment_bytes=$segment_limit
    if ((target_bytes && target_bytes - total_bytes < segment_bytes)); then
        segment_bytes=$((target_bytes - total_bytes))
    fi
    # count_bytes 限制每段的精确字节数，持续持有读取端避免分段时丢失数据。
    dd bs=65536 count="$segment_bytes" iflag=fullblock,count_bytes \
        of="$output_path" oflag=append conv=notrunc status=none \
        <&"$audio_fd" 2> "$work_dir/write.err" &
    writer_pid=$!
    while kill -0 "$writer_pid" 2>/dev/null; do
        (( !stop_requested )) || stop_remote
        if ((stop_sent && SECONDS - stop_started >= 5)); then
            kill -TERM "$adb_pid" 2>/dev/null || :
        fi
        now_ms=$(date +%s%3N)
        if ((now_ms - last_sync_ms >= sync_ms)); then
            refresh_header || fail 'Failed to refresh WAV header.'
            last_sync_ms=$now_ms
        fi
        if ((SECONDS - last_progress >= 5)); then
            size=$(stat -c %s -- "$output_path") || fail 'Cannot read WAV size.'
            awk -v bytes="$((total_bytes + size - 44))" -v rate="$byte_rate" \
                'BEGIN { printf "Recorded %.1fs, %.1f MiB\n", bytes/rate, bytes/1048576 }'
            last_progress=$SECONDS
        fi
        sleep 0.25
    done
    wait "$writer_pid" || {
        cat "$work_dir/write.err" >&2
        fail 'Failed to write WAV data.'
    }
    writer_pid=
    previous_total=$total_bytes
    save_segment || fail 'Failed to finalize WAV data.'
    if ((target_bytes && total_bytes >= target_bytes)); then
        stop_requested=1
    fi
    if ((stop_requested || total_bytes - previous_total < segment_bytes)); then
        break
    fi
    open_segment || fail 'Cannot initialize the next WAV segment.'
done

if ((stop_requested)); then
    stop_remote
    exec {audio_fd}<&-
    audio_fd=
else
    wait "$adb_pid"
    stream_status=$?
    wait "$decoder_pid"
    decoder_status=$?
    ((stream_status == 0)) || {
        cat "$work_dir/adb.err" >&2
        fail "ADB stream exited with code $stream_status."
    }
    ((decoder_status == 0)) || {
        cat "$work_dir/decode.err" >&2
        fail "Audio decoder exited with code $decoder_status."
    }
fi
remote_error=$(adb_control "cat $(remote_quote "$error_file")" 2>/dev/null) || remote_error=
remote_error=${remote_error//$'\r'/}
[[ -z $remote_error ]] || fail "$remote_error"
((total_bytes > 0)) || fail 'The audio stream ended without data.'
printf 'Finished: %s WAV file(s)\n' "$segments_saved"
awk -v bytes="$total_bytes" -v rate="$byte_rate" 'BEGIN { printf "Total duration: %.3fs\n", bytes/rate }'
