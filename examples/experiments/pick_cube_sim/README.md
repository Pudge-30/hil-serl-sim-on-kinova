# Pick Cube Simulation Experiment

This directory contains the configuration and scripts for the "Pick Cube" task in the Franka simulation environment.

## Setup & Requirements

### 1. Create Conda Environment

First, create and activate the conda environment `qyh_hil_serl_sim`:

```bash
conda create -n qyh_hil_serl_sim python=3.10
conda activate qyh_hil_serl_sim
```

### 2. Install Dependencies

Install JAX with GPU support (recommended) or CPU:

```bash
# For GPU (recommended)
pip install --upgrade "jax[cuda12_pip]==0.4.35" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

# Or for CPU
# pip install --upgrade "jax[cpu]"
```

Install the project packages in editable mode. Run these commands from the **project root directory**:

```bash
# Install serl_launcher (must be installed in editable mode first)
cd serl_launcher
pip install -e .
# pip install -r requirements.txt # (Optional, as setup.py handles dependencies)

# Install franka_sim and other dependencies
cd ../franka_sim
pip install -e .
pip install -r requirements.txt

# Install serl_robot_infra (required for franka_env wrappers used in simulation)
cd ../serl_robot_infra
pip install -e .

# Install other required core libraries manually if not picked up
pip install "gym>=0.26" "flax>=0.8.0" "distrax>=0.1.2" "ml_collections>=0.1.0" "chex>=0.1.85" "optax>=0.1.5" "tensorflow>=2.15.0" "tensorflow_probability>=0.23.0" "moviepy>=1.0.3" "gymnasium==0.29.1" "tf-keras" "natsort" "dm_env" "dm-robotics-transformations"

# Return to project root
cd ..
```

## 1. Record Demos (Optional but Recommended)

Recording expert demonstrations helps accelerate training.

Run the following command from the **project root directory**:

```bash
python examples/record_demos_sim.py --exp_name pick_cube_sim --successes_needed 10
```

- **Controls**: Use the joystick/controller to control the robot.
- **Goal**: Pick up the cube and lift it.
- **Output**: Data is saved to `demo_data/`.

## 2. Training (Actor-Learner)

The training process requires two separate terminals.

### Terminal 1: Learner
The learner updates the policy network.

1. Navigate to this directory:
   ```bash
   cd examples/experiments/pick_cube_sim
   ```
2. (Optional) Update `run_learner.sh` to point to your recorded demo file (`--demo_path`).
3. Run:
   ```bash
   # Run on default GPU (0)
   bash run_learner.sh

   # Or specify a GPU ID (e.g., 1)
   bash run_learner.sh --gpu 1
   ```

### Terminal 2: Actor
The actor interacts with the environment and collects data.

1. Navigate to this directory:
   ```bash
   cd examples/experiments/pick_cube_sim
   ```
2. Run:
   ```bash
   # Run on default GPU (0)
   bash run_actor.sh

   # Or specify a GPU ID (e.g., 1)
   bash run_actor.sh --gpu 1
   ```

## 3. Human-in-the-Loop (HIL) Intervention

During training (in the Actor window), you can intervene at any time to correct the robot's behavior using the joystick/controller.

**Intervention Logic:**
- Use the joystick/controller to manually control the robot.
- When you provide input, it immediately overrides the policy action with manual control.
- When you release the controls, it returns control to the policy.
- Use this to guide the robot when it gets stuck or moves incorrectly.

**Note:** Make sure your controller is properly configured. Check `controller_type` (default is xbox) in `examples/experiments/pick_cube_sim/config.py` if your controller is not working.

## 4. 测试手柄连接与功能

在开始训练之前，建议先测试手柄是否正常工作。

### 测试手柄

从项目根目录运行：

```bash
# 测试盖世小鸡启明星2无线手柄（默认）
python examples/experiments/pick_cube_sim/test_controller.py --controller gamesir

# 测试 XBOX 手柄
python examples/experiments/pick_cube_sim/test_controller.py --controller xbox

# 测试 PS5 手柄
python examples/experiments/pick_cube_sim/test_controller.py --controller ps5

# 查看原始手柄事件（用于调试）
python examples/experiments/pick_cube_sim/test_controller.py --raw
```

### 测试程序功能

测试程序会显示：
- **6自由度动作值**：实时显示摇杆和扳机输入
- **按钮状态**：显示夹爪控制按钮（左扳机/右扳机）的状态
- **可视化指示器**：用图形显示摇杆偏移量

### 手柄操作说明

- **左摇杆**：控制机械臂的 X（前后）和 Y（左右）移动
- **右摇杆**：控制机械臂的旋转（RX 和 RY）
- **扳机键**：控制机械臂的 Z（上下）移动
- **左扳机 (BTN_TL)**：关闭夹爪
- **右扳机 (BTN_TR)**：打开夹爪

### 故障排除

如果手柄无法识别：

1. **检查手柄连接**：
   ```bash
   # Linux: 检查设备
   lsusb | grep -i gamepad
   ls /dev/input/
   
   # 检查权限（可能需要将用户添加到 input 组）
   groups
   sudo usermod -a -G input $USER
   ```

2. **查看原始事件**：
   ```bash
   python examples/experiments/pick_cube_sim/test_controller.py --raw
   ```
   这会显示所有手柄事件，帮助诊断问题。

3. **检查配置**：
   如果手柄行为异常，可能需要调整 `serl_robot_infra/franka_env/spacemouse/spacemouse_expert.py` 中的 `GAMESIR` 配置参数（分辨率和缩放因子）。

### 在配置中使用手柄

在 `config.py` 中设置手柄类型：

```python
from franka_env.envs.wrappers import ControllerType

class TrainConfig(DefaultTrainingConfig):
    controller_type = ControllerType.GAMESIR  # 使用盖世小鸡手柄
    # ... 其他配置 ...
```