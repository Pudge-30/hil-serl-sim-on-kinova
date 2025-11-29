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

export CUDA_VISIBLE_DEVICES=$GPU_ID && \
export XLA_PYTHON_CLIENT_PREALLOCATE=false && \
export XLA_PYTHON_CLIENT_MEM_FRACTION=.1 && \
python ../../train_rlpd_sim.py "$@" \
    --exp_name=pick_cube_sim \
    --checkpoint_path=/home/kinova/ssd1/qyh/pick_cube_sim/checkpoint \
    --actor \
