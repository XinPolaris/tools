#!/bin/bash

# 固定项目编号，并复用 fotile_make.sh 的编译选项
PROJECT_NUMBER=19
CCACHE_FLAG="y"
LUNCHENV_FLAG="n"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOTILE_MAKE="$SCRIPT_DIR/fotile_make.sh"

if [ ! -f "$FOTILE_MAKE" ]; then
    echo "错误：未找到 $FOTILE_MAKE，请检查脚本路径。"
    exit 1
fi

# 编号与 fotile_make.sh 中的操作编号保持一致
ACTION_NAMES=(
    "update code(更新项目代码)"
    "update code except SDK(更新除了sdk以外的代码)"
    "make SDK(编译固件包和OTA包)"
    "make SDK firmware(只编译固件包,不编译ota)"
    "make APP(编译主应用)"
    "make APP-OTA(编译ota应用)"
    "make APP-HAL(编译中间件)"
    "make clean(清理编译)"
    "make APP(编译主应用,带调试信息)"
    "make SDK(编译 转测包)"
)

echo "========================================"
echo "项目 $PROJECT_NUMBER 可执行的操作"
echo "========================================"
for index in "${!ACTION_NAMES[@]}"; do
    if [ "$((index + 1))" -eq 9 ]; then
        echo
        echo "调试编译↓↓↓↓↓↓↓↓↓↓↓"
    elif [ "$((index + 1))" -eq 10 ]; then
        echo
        echo "转测包流程↓↓↓↓↓↓↓↓↓↓↓"
    fi
    printf "%d. %s\n" "$((index + 1))" "${ACTION_NAMES[index]}"
done

echo
read -r -a actions -p "请输入要执行的操作编号，多个编号以空格分隔（例如 8 1 3）："

if [ "${#actions[@]}" -eq 0 ] || [ -z "${actions[*]//[[:space:]]/}" ]; then
    echo "错误：未选择任何操作。"
    exit 1
fi

# 执行前一次性校验全部输入，避免部分操作完成后才发现编号错误
for action in "${actions[@]}"; do
    if [[ ! "$action" =~ ^([1-9]|10)$ ]]; then
        echo "错误：无效的操作编号：$action"
        exit 1
    fi
done

cd "$SCRIPT_DIR" || exit 1

for action in "${actions[@]}"; do
    echo
    echo "开始执行 [$action]：${ACTION_NAMES[action - 1]}"
    if ! "$FOTILE_MAKE" \
        "ccache=$CCACHE_FLAG" \
        "lunchenv=$LUNCHENV_FLAG" \
        "lunch_project=$PROJECT_NUMBER" \
        "lunch_compile_type=$action"; then
        echo "错误：操作 $action 执行失败：${ACTION_NAMES[action - 1]}"
        exit 1
    fi
    echo "执行完成 [$action]：${ACTION_NAMES[action - 1]}"
done

echo
echo "所有选定的固件操作均已执行完成。"
