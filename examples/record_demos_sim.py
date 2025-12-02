"""
演示数据录制脚本 (Simulation)

该脚本用于在仿真环境中录制机械臂的演示数据。
通过手柄或SpaceMouse控制机械臂，记录成功的轨迹数据用于后续的强化学习训练。

主要功能：
1. 初始化仿真环境
2. 创建可视化窗口
3. 监听手柄输入并控制机械臂
4. 记录成功的轨迹数据
5. 保存演示数据到文件

使用方法：
    python record_demos_sim.py --exp_name=pick_cube_sim --successes_needed=20
"""

import os
from tqdm import tqdm
import numpy as np
import copy
import pickle as pkl
import datetime
from absl import app, flags
import time

from experiments.mappings import CONFIG_MAPPING
from franka_sim.utils.viewer_utils import DualMujocoViewer

# ============================================================================
# 命令行参数定义
# ============================================================================
FLAGS = flags.FLAGS
flags.DEFINE_string("exp_name", "pick_cube_sim", "实验名称，对应配置文件夹")
flags.DEFINE_integer("successes_needed", 20, "需要收集的成功演示数量")


def main(_):
    """
    主函数：录制演示数据的主流程
    
    流程：
    1. 加载实验配置并创建环境
    2. 初始化可视化窗口
    3. 进入主循环，监听手柄输入并记录轨迹
    4. 只保存成功的轨迹数据
    5. 达到指定数量后保存到文件
    """
    # ========================================================================
    # 1. 环境初始化
    # ========================================================================
    assert FLAGS.exp_name in CONFIG_MAPPING, '实验文件夹未找到'
    config = CONFIG_MAPPING[FLAGS.exp_name]()
    # 创建真实仿真环境（非fake环境，不保存视频，不使用分类器）
    env = config.get_environment(fake_env=False, save_video=False, classifier=False)

    # 重置环境，获取初始观察
    obs, info = env.reset()
    print("环境重置完成")
    
    # ========================================================================
    # 2. 数据记录相关变量初始化
    # ========================================================================
    transitions = []  # 存储所有成功的轨迹转换数据
    success_count = 0  # 成功演示计数
    success_needed = FLAGS.successes_needed  # 需要的成功演示数量
    pbar = tqdm(total=success_needed)  # 进度条
    trajectory = []  # 当前轨迹的转换数据
    returns = 0  # 当前轨迹的累计奖励
    
    # ========================================================================
    # 3. 可视化窗口初始化
    # ========================================================================
    # 创建双窗口Mujoco查看器（用于显示仿真环境）
    dual_viewer = DualMujocoViewer(env.unwrapped.model, env.unwrapped.data)

    # 尝试将查看器附加到支持它的任何包装器上
    # 遍历环境包装器链，找到支持attach_viewer的环境
    current_env = env
    while True:
        if hasattr(current_env, 'attach_viewer'):
            current_env.attach_viewer(dual_viewer.viewer_1)
        
        # 检查是否有内部环境（环境包装器模式）
        if hasattr(current_env, 'env'):
            current_env = current_env.env
        else:
            break

    # ========================================================================
    # 4. 主循环：监听输入并记录数据
    # ========================================================================
    print("按Shift键开始录制。\n注意：本系统仅支持盖世小鸡启明星2无线手柄。如果手柄无法工作，请检查手柄连接。")
    
    # 动作阈值：过滤掉过小的动作（可能是噪声或手柄偏移）
    action_threshold = 0.01  # 如果动作的L2范数小于此值，视为无效动作
    
    # 统计信息
    total_steps = 0
    recorded_steps = 0
    zero_action_steps = 0
    
    with dual_viewer as viewer:
        while viewer.is_running():
            # 默认动作为零（等待手柄输入）
            actions = np.zeros(env.action_space.sample().shape) 
            
            # 执行动作，获取下一步观察和奖励
            next_obs, rew, done, truncated, info = env.step(actions)
            
            # 同步可视化窗口
            viewer.sync()
            
            # 累计奖励
            returns += rew
            
            # 统计总步数
            total_steps += 1
            
            # 如果info中包含intervene_action，说明有手柄输入，使用该动作
            # 这通常由环境包装器（如JoystickIntervention）提供
            # 注意：intervene_action已经在RelativeFrame中被转换到末端执行器坐标系
            has_intervention = "intervene_action" in info
            if has_intervention:
                actions = info["intervene_action"].copy()  # 使用copy避免引用问题
                
                # 检查动作是否有效（过滤噪声和手柄偏移）
                action_norm = np.linalg.norm(actions[:6])  # 只检查6DOF动作，不包括夹爪
                if action_norm < action_threshold:
                    # 动作太小，视为无效，不保存
                    zero_action_steps += 1
                    obs = next_obs
                    if done:
                        # 处理轨迹结束
                        if info["succeed"]:
                            # 即使有无效动作，如果轨迹成功，也要保存（但使用零动作）
                            # 这确保轨迹的完整性
                            transition = copy.deepcopy(
                                dict(
                                    observations=obs,
                                    actions=np.zeros_like(actions),  # 使用零动作
                                    next_observations=next_obs,
                                    rewards=rew,
                                    masks=1.0 - done,
                                    dones=done,
                                    infos=info,
                                )
                            )
                            trajectory.append(transition)
                        # 重置轨迹相关变量
                        trajectory = []
                        returns = 0
                        obs, info = env.reset()
                    
                    # 如果达到所需成功数量，退出循环
                    if success_count >= success_needed:
                        break
                    continue
            
            # 只有在有有效手柄输入时才保存数据
            # 这样可以避免保存大量零动作，导致策略学习到错误的偏好
            if has_intervention and np.linalg.norm(actions[:6]) >= action_threshold:
            # 创建转换数据字典（用于离线强化学习）
            transition = copy.deepcopy(
                dict(
                    observations=obs,          # 当前观察
                        actions=actions,            # 执行的动作（已在末端执行器坐标系中）
                    next_observations=next_obs, # 下一步观察
                    rewards=rew,                # 即时奖励
                    masks=1.0 - done,           # 掩码（done时为0，否则为1）
                    dones=done,                 # 是否结束
                    infos=info,                 # 额外信息
                )
            )
            trajectory.append(transition)
                recorded_steps += 1
            elif done and info.get("succeed", False) and len(trajectory) > 0:
                # 没有有效手柄输入，但如果是轨迹结束且成功，需要保存最后一个transition以保持轨迹完整性
                # 保存最后一个transition（使用零动作）
                transition = copy.deepcopy(
                    dict(
                        observations=obs,
                        actions=np.zeros_like(actions),
                        next_observations=next_obs,
                        rewards=rew,
                        masks=1.0 - done,
                        dones=done,
                        infos=info,
                    )
                )
                trajectory.append(transition)
            
            # 更新进度条描述（显示当前累计奖励和统计信息）
            pbar.set_description(
                f"累计奖励: {returns:.2f} | "
                f"记录: {recorded_steps}/{total_steps} | "
                f"零动作: {zero_action_steps}"
            )

            # 更新观察
            obs = next_obs
            
            # ================================================================
            # 5. 处理轨迹结束
            # ================================================================
            if done:
                # 如果任务成功完成，保存该轨迹
                if info["succeed"]:
                    # 将成功的轨迹添加到总数据集中（使用extend提高效率）
                    transitions.extend([copy.deepcopy(transition) for transition in trajectory])
                    success_count += 1
                    print(f"成功计数: {success_count} | 轨迹长度: {len(trajectory)}")
                    pbar.update(1)  # 更新进度条
                
                # 重置轨迹相关变量
                trajectory = []
                returns = 0
                obs, info = env.reset()
            
            # 如果达到所需成功数量，退出循环
            if success_count >= success_needed:
                break
    
    # ========================================================================
    # 6. 关闭环境和viewer（在保存数据之前）
    # ========================================================================
    # 关闭viewer上下文（这会调用viewer.close()）
    # 注意：viewer.close()会调用glfw.terminate()，所以在关闭viewer后
    # 不能再使用任何需要GLFW的操作（如环境重置等）
    
    # 关闭环境（如果环境有close方法）
    if hasattr(env, 'close'):
        try:
            env.close()
        except Exception as e:
            print(f"关闭环境时出现警告: {e}")
    
    # ========================================================================
    # 7. 保存演示数据并输出统计信息
    # ========================================================================
    # 确保demo_data目录存在
    if not os.path.exists("./demo_data"):
        os.makedirs("./demo_data")
    
    # 生成带时间戳的文件名
    uuid = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"./demo_data/{FLAGS.exp_name}_{success_needed}_demos_{uuid}.pkl"
    
    # 计算数据统计信息
    if len(transitions) > 0:
        all_actions = np.array([t["actions"] for t in transitions])
        action_mean = np.mean(all_actions, axis=0)
        action_std = np.std(all_actions, axis=0)
        action_norms = np.linalg.norm(all_actions[:, :6], axis=1)  # 只检查6DOF
        
        print("\n" + "=" * 80)
        print("数据统计信息:")
        print(f"  总transition数: {len(transitions)}")
        print(f"  总步数: {total_steps}")
        print(f"  记录步数: {recorded_steps} ({100*recorded_steps/total_steps:.1f}%)")
        print(f"  零动作步数: {zero_action_steps}")
        print(f"\n动作统计 (6DOF):")
        print(f"  均值: {action_mean[:6]}")
        print(f"  标准差: {action_std[:6]}")
        print(f"  动作L2范数均值: {np.mean(action_norms):.4f}")
        print(f"  动作L2范数标准差: {np.std(action_norms):.4f}")
        print(f"\n夹爪动作统计:")
        if all_actions.shape[1] > 6:
            gripper_actions = all_actions[:, 6]
            print(f"  均值: {np.mean(gripper_actions):.4f}")
            print(f"  标准差: {np.std(gripper_actions):.4f}")
            print(f"  关闭次数: {np.sum(gripper_actions < -0.5)}")
            print(f"  打开次数: {np.sum(gripper_actions > 0.5)}")
            print(f"  无操作次数: {np.sum(np.abs(gripper_actions) <= 0.5)}")
        
        # 检查是否有明显的动作偏差
        if np.any(np.abs(action_mean[:6]) > 0.05):
            print("\n⚠️  警告: 检测到动作均值明显非零，可能存在以下问题:")
            print("  1. 手柄物理偏移（摇杆不在中心位置）")
            print("  2. 数据集中某个方向的样本过多")
            print("  3. 坐标系转换问题")
            for i, (mean, std) in enumerate(zip(action_mean[:6], action_std[:6])):
                if abs(mean) > 0.05:
                    dim_names = ["Y平移", "X平移", "Z平移", "Roll", "Pitch", "Yaw"]
                    print(f"    - {dim_names[i]}: 均值={mean:.4f}, 标准差={std:.4f}")
        else:
            print("\n✓ 动作均值接近零，数据质量良好")
        print("=" * 80 + "\n")
    
    # 保存数据到pickle文件
    with open(file_name, "wb") as f:
        pkl.dump(transitions, f)
        print(f"已保存 {success_needed} 个演示到 {file_name}")

if __name__ == "__main__":
    app.run(main)