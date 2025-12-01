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
            
            # 如果info中包含intervene_action，说明有手柄输入，使用该动作
            # 这通常由环境包装器（如ExpertActionWrapper）提供
            if "intervene_action" in info:
                actions = info["intervene_action"]
            
            # 创建转换数据字典（用于离线强化学习）
            transition = copy.deepcopy(
                dict(
                    observations=obs,          # 当前观察
                    actions=actions,            # 执行的动作
                    next_observations=next_obs, # 下一步观察
                    rewards=rew,                # 即时奖励
                    masks=1.0 - done,           # 掩码（done时为0，否则为1）
                    dones=done,                 # 是否结束
                    infos=info,                 # 额外信息
                )
            )
            trajectory.append(transition)
            
            # 更新进度条描述（显示当前累计奖励）
            pbar.set_description(f"累计奖励: {returns}")

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
                    print(f"成功计数: {success_count}")
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
    # 7. 保存演示数据
    # ========================================================================
    # 确保demo_data目录存在
    if not os.path.exists("./demo_data"):
        os.makedirs("./demo_data")
    
    # 生成带时间戳的文件名
    uuid = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"./demo_data/{FLAGS.exp_name}_{success_needed}_demos_{uuid}.pkl"
    
    # 保存数据到pickle文件
    with open(file_name, "wb") as f:
        pkl.dump(transitions, f)
        print(f"已保存 {success_needed} 个演示到 {file_name}")

if __name__ == "__main__":
    app.run(main)