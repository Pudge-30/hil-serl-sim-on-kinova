#!/bin/bash

# Default GPU
GPU_ID=0

# Parse arguments for --gpu
args=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --gpu)
            GPU_ID="$2"
            shift 2
            ;;
        *)
            args+=("$1")
            shift
            ;;
    esac
done

# Set the remaining arguments back
set -- "${args[@]}"

# ========================================================================
# 自动选择最新的demo文件
# ========================================================================
# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录（从examples/experiments/pick_cube_sim向上两级）
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEMO_DATA_DIR="$PROJECT_ROOT/demo_data"
DEMO_PATH=""

# 调试信息（可选，可以通过环境变量控制）
if [ "${DEBUG_DEMO_SEARCH:-0}" = "1" ]; then
    echo "调试信息:"
    echo "  脚本目录: $SCRIPT_DIR"
    echo "  项目根目录: $PROJECT_ROOT"
    echo "  Demo目录: $DEMO_DATA_DIR"
    echo "  Demo目录是否存在: $([ -d "$DEMO_DATA_DIR" ] && echo "是" || echo "否")"
fi

# 检查demo_data目录是否存在
if [ -d "$DEMO_DATA_DIR" ]; then
    # 使用shopt来确保通配符正确展开
    shopt -s nullglob
    # 查找所有.pkl文件（使用数组来避免空格问题）
    PKL_FILES=("$DEMO_DATA_DIR"/*.pkl)
    shopt -u nullglob
    
    # 检查是否找到文件
    if [ ${#PKL_FILES[@]} -gt 0 ] && [ -e "${PKL_FILES[0]}" ]; then
        # 找到最新的.pkl文件（按修改时间排序）
        # 使用stat命令获取修改时间并排序
        LATEST_DEMO=""
        LATEST_TIME=0
        
        for file in "${PKL_FILES[@]}"; do
            if [ -f "$file" ]; then
                # 获取文件的修改时间（Unix时间戳）
                FILE_TIME=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)
                if [ -n "$FILE_TIME" ] && [ "$FILE_TIME" -gt "$LATEST_TIME" ]; then
                    LATEST_TIME=$FILE_TIME
                    LATEST_DEMO="$file"
                fi
            fi
        done
        
        if [ -n "$LATEST_DEMO" ] && [ -f "$LATEST_DEMO" ]; then
            # 使用相对路径（从项目根目录）
            DEMO_PATH=$(basename "$LATEST_DEMO")
            echo "=========================================="
            echo "找到最新的demo文件: $DEMO_PATH"
            echo "完整路径: $LATEST_DEMO"
            echo "使用路径: demo_data/$DEMO_PATH"
            echo "=========================================="
        fi
    else
        if [ "${DEBUG_DEMO_SEARCH:-0}" = "1" ]; then
            echo "  未找到.pkl文件"
            echo "  目录内容:"
            ls -la "$DEMO_DATA_DIR" 2>/dev/null || echo "    无法列出目录内容"
        fi
    fi
else
    if [ "${DEBUG_DEMO_SEARCH:-0}" = "1" ]; then
        echo "  Demo目录不存在: $DEMO_DATA_DIR"
    fi
fi

# 如果未找到demo文件，显示警告
if [ -z "$DEMO_PATH" ]; then
    echo "警告: 未找到demo文件，将不使用demo数据进行训练"
    echo "提示: 请先运行 'python examples/record_demos_sim.py --exp_name pick_cube_sim --successes_needed 10' 采集demo"
    echo "      Demo目录路径: $DEMO_DATA_DIR"
    echo "      如需调试，请设置环境变量: DEBUG_DEMO_SEARCH=1 bash run_learner.sh"
fi

# 设置环境变量
export CUDA_VISIBLE_DEVICES=$GPU_ID
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_MEM_FRACTION=.3

# 构建训练命令参数
TRAIN_ARGS=(
    "$@"
    --exp_name=pick_cube_sim
    --checkpoint_path=/home/kinova/ssd1/qyh/pick_cube_sim/checkpoint
    --learner
)

# 如果找到了demo文件，添加--demo_path参数
if [ -n "$DEMO_PATH" ]; then
    TRAIN_ARGS+=(--demo_path="demo_data/$DEMO_PATH")
fi

# 执行训练命令
python ../../train_rlpd_sim.py "${TRAIN_ARGS[@]}"

