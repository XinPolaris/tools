#!/bin/sh

VIDEO1="https://fiksvideo.fotile.com.cn/recipe_videos/20260403164812_recipe_20260403_164811.mp4"
VIDEO2="https://fiksvideo.fotile.com.cn/recipe_videos/20260428153329_recipe_20260428_153328.mp4"
VIDEO3="https://fiksvideo.fotile.com.cn/0592362585c04bcc82489a8efb7018a5"

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
	echo ">>>start playing:$l" >&2
    url="$1"

    echo "==============================" >&2
    echo "[PLAY] $url" >&2
    echo "==============================" >&2

    # 进入播放页
    send_cmd "play url:$url"

    # 观看 5~10 秒
    wait_random 10 15

    # 退出页面，应用端 reset
    send_cmd "reset"

    # reset 后等待 2 秒
    echo "[WAIT] 2s" >&2
    sleep 2
	echo "<<< Finished:$l" >&2
}

{
    # 等 tplayerdemo 初始化完成
    sleep 6

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