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