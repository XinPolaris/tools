#!/bin/sh

SEEK_COUNT=5

VIDEO1="https://fiksvideo.fotile.com.cn/recipe_videos/20260403164812_recipe_20260403_164811.mp4"
VIDEO2="https://fiksvideo.fotile.com.cn/recipe_videos/20260428153329_recipe_20260428_153328.mp4"
VIDEO3="https://fiksvideo.fotile.com.cn/recipe_videos/20260428154353_recipe_20260428_154352.mp4"

send_cmd()
{
    echo "[CMD] $1" >&2
    echo "$1"
}

rand_range()
{
    min=$1
    max=$2

    n=$(od -An -N2 -tu2 /dev/urandom 2>/dev/null | tr -d ' ')
    if [ -z "$n" ]; then
        n=$(date +%s)
    fi

    echo $((min + n % (max - min + 1)))
}

rand_seek()
{
    rand_range 0 20
}

wait_random()
{
    min=$1
    max=$2
    sec=$(rand_range "$min" "$max")
    echo "[WAIT] ${sec}s" >&2
    sleep "$sec"
}

play_one()
{
    url="$1"

    echo "==============================" >&2
    echo "[PLAY] $url" >&2
    echo "==============================" >&2

    send_cmd "play url:$url"

    # 模拟 App 打开视频后的加载和起播等待
    wait_random 5 8

    i=0
    while [ "$i" -lt "$SEEK_COUNT" ]
    do
        sec=$(rand_seek)
        send_cmd "seek to:$sec"

        # 模拟用户拖动进度条后继续观看
        wait_random 3 6

        i=$((i + 1))
    done

    # 最后再看一会儿
    wait_random 5 10

    send_cmd "reset"

    # 模拟退出当前播放页、切换下一个视频
    wait_random 2 3
}

{
    # 进入 tplayerdemo 后只执行一次
    send_cmd "set volume:50"
    sleep 1

    while true
    do
        play_one "$VIDEO1"
        play_one "$VIDEO2"
        play_one "$VIDEO3"
    done
} | tplayerdemo