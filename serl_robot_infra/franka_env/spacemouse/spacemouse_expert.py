"""
手柄和SpaceMouse输入设备接口模块

该模块提供了两种输入设备的接口：
1. SpaceMouseExpert: 用于3DConnexion SpaceMouse设备
2. JoystickExpert: 用于盖世小鸡启明星2无线手柄

两个类都使用多进程架构，在后台持续读取输入设备状态，
并通过共享内存提供非阻塞的get_action接口。

主要特性：
- 多进程架构，避免阻塞主程序
- 支持盖世小鸡启明星2无线手柄
- 自动归一化和缩放输入值
- 自动检测有符号/无符号值范围
- 线程安全的状态共享
"""

import time
import multiprocessing
import numpy as np
import inputs
from franka_env.spacemouse import pyspacemouse
from typing import Tuple
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# SpaceMouseExpert 类
# ============================================================================
class SpaceMouseExpert:
    """
    This class provides an interface to the SpaceMouse.
    It continuously reads the SpaceMouse state and provides
    a "get_action" method to get the latest action and button state.
    """

    def __init__(self):
        """
        初始化SpaceMouseExpert
        
        功能：
        - 打开SpaceMouse设备连接
        - 创建多进程管理器用于共享状态
        - 启动后台进程持续读取设备状态
        """
        pyspacemouse.open()

        # 创建多进程管理器，用于在进程间共享状态
        self.manager = multiprocessing.Manager()
        self.latest_data = self.manager.dict()
        # action: 6DOF动作 [x, y, z, roll, pitch, yaw]
        self.latest_data["action"] = [0.0] * 6  # 使用列表以兼容多进程
        # buttons: 按钮状态列表
        self.latest_data["buttons"] = [0, 0, 0, 0]

        # 启动后台进程持续读取SpaceMouse状态
        self.process = multiprocessing.Process(target=self._read_spacemouse)
        self.process.daemon = True  # 守护进程，主程序退出时自动终止
        self.process.start()

    def _read_spacemouse(self):
        """
        后台进程：持续读取SpaceMouse状态
        
        该函数在独立进程中运行，不断读取SpaceMouse的输入状态
        并更新共享内存中的数据，供主进程通过get_action()获取。
        
        动作映射：
        - action[0-2]: 平移 (x, y, z)
        - action[3-5]: 旋转 (roll, pitch, yaw)
        """
        while True:
            # 读取所有SpaceMouse设备的状态（可能连接多个设备）
            state = pyspacemouse.read_all()
            action = [0.0] * 6
            buttons = [0, 0, 0, 0]

            # 如果连接了两个SpaceMouse设备，合并它们的输入
            if len(state) == 2:
                action = [
                    -state[0].y, state[0].x, state[0].z,  # 设备1的平移
                    -state[0].roll, -state[0].pitch, -state[0].yaw,  # 设备1的旋转
                    -state[1].y, state[1].x, state[1].z,  # 设备2的平移
                    -state[1].roll, -state[1].pitch, -state[1].yaw  # 设备2的旋转
                ]
                buttons = state[0].buttons + state[1].buttons
            # 如果只连接了一个设备
            elif len(state) == 1:
                action = [
                    -state[0].y, state[0].x, state[0].z,  # 平移 (注意y轴取反)
                    -state[0].roll, -state[0].pitch, -state[0].yaw  # 旋转（全部取反）
                ]
                buttons = state[0].buttons

            # 更新共享状态（主进程可以通过latest_data访问）
            self.latest_data["action"] = action
            self.latest_data["buttons"] = buttons

    def get_action(self) -> Tuple[np.ndarray, list]:
        """
        获取最新的动作和按钮状态
        
        Returns:
            Tuple[np.ndarray, list]: 
                - action: 6DOF动作数组 [x, y, z, roll, pitch, yaw]
                - buttons: 按钮状态列表
        """
        action = self.latest_data["action"]
        buttons = self.latest_data["buttons"]
        return np.array(action), buttons
    
    def close(self):
        """
        关闭SpaceMouse连接并终止后台进程
        """
        # pyspacemouse.close()  # 注释掉，避免关闭问题
        self.process.terminate()

# ============================================================================
# 手柄类型和配置
# ============================================================================
class ControllerType(Enum):
    """支持的手柄类型枚举"""
    GAMESIR = "gamesir"  # 盖世小鸡启明星2无线手柄

@dataclass
class ControllerConfig:
    """
    手柄配置数据类
    
    Attributes:
        resolution: 各轴的分辨率（用于归一化）
        scale: 各轴的缩放因子（用于调整灵敏度）
    """
    resolution: dict  # 例如: {'ABS_X': 2**16, 'ABS_Y': 2**16, ...}
    scale: dict       # 例如: {'ABS_X': -0.1, 'ABS_Y': -0.1, ...}

# ============================================================================
# JoystickExpert 类
# ============================================================================
class JoystickExpert:
    """
    This class provides an interface to the Joystick/Gamepad.
    It continuously reads the joystick state and provides
    a "get_action" method to get the latest action and button state.
    """

    # ========================================================================
    # 手柄配置
    # ========================================================================
    # 盖世小鸡启明星2无线手柄配置
    # 配置包含：
    #   - resolution: 各轴的原始分辨率范围（用于归一化）
    #   - scale: 各轴的缩放因子（控制灵敏度，决定最大速度）
    CONTROLLER_CONFIG = ControllerConfig(
        # 盖世小鸡启明星2无线手柄：所有摇杆和扳机均使用 8 位分辨率 [0, 255]
        resolution={
            'ABS_X': 256,       # 左摇杆 X 轴（8位，范围0-255）
            'ABS_Y': 256,       # 左摇杆 Y 轴（8位，范围0-255）
            'ABS_RX': 256,      # 右摇杆 X 轴（8位，范围0-255）
            'ABS_RY': 256,      # 右摇杆 Y 轴（8位，范围0-255）
            'ABS_Z': 256,       # 左扳机（8位，范围0-255）
            'ABS_RZ': 256,      # 右扳机（8位，范围0-255）
            'ABS_HAT0X': 1.0,   # D-pad X 轴
        },
        scale={
            'ABS_X': -0.15,     # 左摇杆 X 轴最大速度（负号表示方向）
            'ABS_Y': -0.15,     # 左摇杆 Y 轴最大速度
            'ABS_RX': 0.25,     # 右摇杆 X 轴最大速度（用于旋转）
            'ABS_RY': 0.25,     # 右摇杆 Y 轴最大速度（用于旋转）
            'ABS_Z': 0.1,       # 左扳机最大速度
            'ABS_RZ': 0.1,      # 右扳机最大速度
            'ABS_HAT0X': 0.3,   # D-pad 最大速度
        }
    )

    def __init__(self, controller_type=ControllerType.GAMESIR):
        """
        初始化JoystickExpert
        
        Args:
            controller_type: 手柄类型，默认为GAMESIR（盖世小鸡启明星2无线手柄）
        """
        self.controller_type = controller_type
        self.controller_config = self.CONTROLLER_CONFIG

        # 创建多进程管理器，用于在进程间共享状态
        self.manager = multiprocessing.Manager()
        self.latest_data = self.manager.dict()
        # action: 6DOF动作 [x, y, z, roll, pitch, yaw]
        self.latest_data["action"] = [0.0] * 6
        # buttons: 按钮状态 [左扳机, 右扳机]
        self.latest_data["buttons"] = [False, False]

        # 启动后台进程持续读取手柄状态
        self.process = multiprocessing.Process(target=self._read_joystick)
        self.process.daemon = True  # 守护进程
        self.process.start()

    def _read_joystick(self):        
        """
        后台进程：持续读取手柄状态
        
        该函数在独立进程中运行，不断读取手柄输入事件，
        进行归一化和缩放处理，然后更新共享内存。
        
        归一化方式（8位无符号 [0, 255]）：
        
        摇杆归一化：
        - 中心值：127.5
        - 归一化公式：normalized = (raw_value - 127.5) / 127.5
        - 当 raw_value = 127.5（中心）时，normalized = 0，机械臂静止
        - 当 raw_value = 0（最小）时，normalized = -1
        - 当 raw_value = 255（最大）时，normalized = 1
        - 速度与摇杆角度呈线性关系：speed = normalized * scale
        
        扳机归一化（ABS_Z, ABS_RZ）：
        - 松开时：raw_value ≈ 0，normalized = 0，机械臂不动
        - 按下时：raw_value ≈ 255，normalized = 1
        - 归一化公式：normalized = raw_value / 255.0
        - ABS_Z按下：机械臂上升（action[2] = normalized * scale，正值）
        - ABS_RZ按下：机械臂下降（action[2] = -normalized * scale，负值）
        - 同时按下：机械臂不动（action[2] = 0）
        
        动作映射：
        - action[0]: ABS_Y (左摇杆Y轴) -> 机械臂Y轴平移
        - action[1]: ABS_X (左摇杆X轴) -> 机械臂X轴平移
        - action[2]: ABS_Z/ABS_RZ (扳机) -> 机械臂Z轴平移
          - ABS_Z按下：上升（正值）
          - ABS_RZ按下：下降（负值）
          - 同时按下：不动（0）
        - action[3]: ABS_RX (右摇杆X轴) -> 机械臂Roll旋转
        - action[4]: ABS_RY (右摇杆Y轴) -> 机械臂Pitch旋转
        - action[5]: ABS_HAT0X (D-pad) -> 机械臂Yaw旋转
        """
        # 初始化 action 和 buttons，保持状态在循环外（避免每次循环重置）
        action = [0.0] * 6
        buttons = [False, False]
        
        # 死区阈值：小于此值的归一化输入将被视为0（过滤噪声）
        # 对于8位分辨率 [0, 255]，中心值127.5
        # 死区0.05意味着：|(raw_value - 127.5) / 127.5| < 0.05
        # 即 raw_value 在 [121.125, 133.875] 范围内时被视为中心，机械臂静止
        deadzone = 0.05  # 5%死区，确保摇杆居中时静止不动
        
        # 存储每个轴的当前原始值和最后更新时间
        axis_values = {}
        axis_last_update = {}  # 记录每个轴最后更新的时间
        
        # 定义需要监控的所有轴及其对应的action索引
        axis_to_action = {
            'ABS_Y': 0,    # 左摇杆Y轴 -> 动作[0]
            'ABS_X': 1,    # 左摇杆X轴 -> 动作[1]
            'ABS_RZ': 2,  # 右扳机 -> 动作[2]（向上）
            'ABS_Z': 2,   # 左扳机 -> 动作[2]（向下）
            'ABS_RX': 3,  # 右摇杆X轴 -> 动作[3]（Roll）
            'ABS_RY': 4,  # 右摇杆Y轴 -> 动作[4]（Pitch）
            'ABS_HAT0X': 5,  # D-pad X轴 -> 动作[5]（Yaw）
        }
        
        # 超时时间：如果某个轴超过这个时间没有更新，且当前action不为0，则重置为0
        axis_timeout = 0.15  # 150ms
        last_check_time = time.time()
        
        while True:
            try:
                current_time = time.time()
                # 获取手柄事件
                # inputs.get_gamepad() 返回一个生成器，需要遍历
                # 如果没有事件，生成器为空，循环不会执行
                events = inputs.get_gamepad()
                
                has_events = False
                # 处理每个事件
                for event in events:
                    has_events = True
                    # 处理摇杆和扳机轴事件
                    if event.code in self.controller_config.resolution:
                        # 存储当前轴的原始值和更新时间
                        raw_value = event.state
                        axis_values[event.code] = raw_value
                        axis_last_update[event.code] = current_time
                        
                        # 归一化手柄输入值
                        resolution = self.controller_config.resolution[event.code]
                        
                        # 扳机使用特殊的归一化：范围 [0, 255]，松开时0，按下时255
                        # 对于扳机（ABS_Z, ABS_RZ），归一化到 [0, 1] 范围
                        if event.code in ['ABS_Z', 'ABS_RZ']:
                            # 扳机归一化：normalized = raw_value / 255.0
                            # 当 raw_value = 0（松开）时，normalized = 0，机械臂不动
                            # 当 raw_value = 255（按下）时，normalized = 1
                            max_value = 255.0
                            normalized_value = raw_value / max_value
                            
                            # 扳机死区：如果值太小（接近0），视为松开
                            trigger_deadzone = 0.05  # 5%，对应raw_value约12.75
                            is_in_deadzone = normalized_value < trigger_deadzone
                            if is_in_deadzone:
                                normalized_value = 0.0
                        else:
                            # 摇杆使用标准归一化：范围 [0, 255]，中心值 127.5
                            # 对于8位分辨率，实际范围是 [0, 255]，中心值是 127.5
                            if resolution == 256:
                                # 8位：范围 [0, 255]，中心值 127.5
                                center = 127.5
                                half_range = 127.5
                            else:
                                # 其他分辨率（如D-pad）
                                center = resolution / 2
                                half_range = center
                            
                            # 无符号归一化：normalized = (raw_value - center) / half_range
                            # 当 raw_value = 127.5（中心）时，normalized = 0，机械臂静止
                            # 当 raw_value = 0（最小）时，normalized = -1
                            # 当 raw_value = 255（最大）时，normalized = 1
                            # 速度与摇杆角度呈线性关系：speed = normalized * scale
                            normalized_value = (raw_value - center) / half_range
                            
                            # 应用死区：如果值太小，视为0（摇杆在中心位置）
                            # 这确保摇杆居中时机械臂静止不动
                            is_in_deadzone = abs(normalized_value) < deadzone
                            if is_in_deadzone:
                                normalized_value = 0.0
                        
                        # 应用缩放因子（控制最大速度）
                        # 对于摇杆：normalized 范围 [-1, 1]，scale 决定最大速度
                        # 对于扳机：normalized 范围 [0, 1]，scale 决定最大速度
                        scaled_value = normalized_value * self.controller_config.scale[event.code]

                        # 将手柄输入映射到6DOF动作
                        # 速度与摇杆角度呈线性关系：action = normalized * scale
                        # 如果值在死区内，直接设置为0，确保摇杆居中时静止不动
                        if event.code == 'ABS_Y':
                            # 左摇杆Y轴 -> 动作[0]（Y轴平移）
                            action[0] = 0.0 if is_in_deadzone else scaled_value
                        elif event.code == 'ABS_X':
                            # 左摇杆X轴 -> 动作[1]（X轴平移）
                            action[1] = 0.0 if is_in_deadzone else scaled_value
                        elif event.code == 'ABS_Z':
                            # 左扳机（ABS_Z）-> 动作[2]（Z轴平移，向上，正值）
                            # 按下ABS_Z时，机械臂上升
                            if is_in_deadzone:
                                # 如果左扳机松开，重置对应的action值
                                # 但需要检查右扳机是否也在使用
                                if 'ABS_RZ' in axis_values:
                                    rz_raw = axis_values['ABS_RZ']
                                    rz_normalized = rz_raw / 255.0
                                    if rz_normalized < 0.05:  # 右扳机也松开
                                        action[2] = 0.0
                                    else:
                                        # 右扳机还在使用，机械臂下降
                                        action[2] = -rz_normalized * self.controller_config.scale['ABS_RZ']
                                else:
                                    action[2] = 0.0
                            else:
                                # 左扳机按下，机械臂上升（正值）
                                abs_z_value = scaled_value
                                
                                # 检查右扳机是否也在使用
                                if 'ABS_RZ' in axis_values:
                                    rz_raw = axis_values['ABS_RZ']
                                    rz_normalized = rz_raw / 255.0
                                    if rz_normalized >= 0.05:  # 右扳机也按下
                                        # 同时按下，机械臂不动
                                        action[2] = 0.0
                                    else:
                                        # 只有左扳机按下，机械臂上升
                                        action[2] = abs_z_value
                                else:
                                    # 只有左扳机按下，机械臂上升
                                    action[2] = abs_z_value
                        elif event.code == 'ABS_RZ':
                            # 右扳机（ABS_RZ）-> 动作[2]（Z轴平移，向下，负值）
                            # 按下ABS_RZ时，机械臂下降
                            if is_in_deadzone:
                                # 如果右扳机松开，重置对应的action值
                                # 但需要检查左扳机是否也在使用
                                if 'ABS_Z' in axis_values:
                                    z_raw = axis_values['ABS_Z']
                                    z_normalized = z_raw / 255.0
                                    if z_normalized < 0.05:  # 左扳机也松开
                                        action[2] = 0.0
                                    else:
                                        # 左扳机还在使用，机械臂上升
                                        action[2] = z_normalized * self.controller_config.scale['ABS_Z']
                                else:
                                    action[2] = 0.0
                            else:
                                # 右扳机按下，机械臂下降（负值）
                                abs_rz_value = -scaled_value
                                
                                # 检查左扳机是否也在使用
                                if 'ABS_Z' in axis_values:
                                    z_raw = axis_values['ABS_Z']
                                    z_normalized = z_raw / 255.0
                                    if z_normalized >= 0.05:  # 左扳机也按下
                                        # 同时按下，机械臂不动
                                        action[2] = 0.0
                                    else:
                                        # 只有右扳机按下，机械臂下降
                                        action[2] = abs_rz_value
                                else:
                                    # 只有右扳机按下，机械臂下降
                                    action[2] = abs_rz_value
                        elif event.code == 'ABS_RX':
                            # 右摇杆X轴 -> 动作[3]（Roll旋转）
                            action[3] = 0.0 if is_in_deadzone else scaled_value
                        elif event.code == 'ABS_RY':
                            # 右摇杆Y轴 -> 动作[4]（Pitch旋转）
                            action[4] = 0.0 if is_in_deadzone else scaled_value
                        elif event.code == 'ABS_HAT0X':
                            # D-pad X轴 -> 动作[5]（Yaw旋转）
                            action[5] = 0.0 if is_in_deadzone else scaled_value
                        
                    # 处理按钮事件
                    elif event.code == 'BTN_TL':
                        buttons[0] = bool(event.state)  # 左扳机按钮
                    elif event.code == 'BTN_TR':
                        buttons[1] = bool(event.state)  # 右扳机按钮
                
                # 定期检查：如果某个轴长时间没有更新，检查是否需要重置
                # 这可以处理摇杆回到中心但没有发送事件的情况
                if current_time - last_check_time > 0.1:  # 每100ms检查一次
                    # 检查所有摇杆轴（不包括扳机，因为扳机可能一直保持按下状态）
                    for axis_code in ['ABS_X', 'ABS_Y', 'ABS_RX', 'ABS_RY', 'ABS_HAT0X']:
                        if axis_code in axis_values and axis_code in axis_last_update:
                            # 如果该轴超过超时时间没有更新
                            if current_time - axis_last_update[axis_code] > axis_timeout:
                                action_idx = axis_to_action[axis_code]
                                raw_value = axis_values[axis_code]
                                
                                # 检查原始值是否在中心位置（8位：中心值127.5，死区范围约[121, 134]）
                                # 如果原始值在中心位置，说明摇杆已经回到中心，应该重置action
                                center_value = 127.5
                                center_tolerance = 127.5 * deadzone  # 约6.375
                                is_near_center = abs(raw_value - center_value) < center_tolerance
                                
                                # 如果原始值在中心位置，或者action值不为0，则重置
                                if is_near_center or abs(action[action_idx]) > 0.001:
                                    action[action_idx] = 0.0
                    
                    # 特殊处理扳机：如果扳机长时间没有更新，检查是否需要重置
                    # 对于扳机，松开时值接近0，按下时值接近255
                    trigger_deadzone_raw = 12.75  # 5% * 255，对应扳机死区
                    
                    if 'ABS_RZ' in axis_values and 'ABS_RZ' in axis_last_update:
                        if current_time - axis_last_update['ABS_RZ'] > axis_timeout:
                            rz_raw = axis_values['ABS_RZ']
                            # 如果右扳机松开（值接近0），或者action[2]是负值，则重置
                            if rz_raw < trigger_deadzone_raw:
                                # 右扳机松开，检查左扳机状态
                                if 'ABS_Z' in axis_values:
                                    z_raw = axis_values['ABS_Z']
                                    if z_raw < trigger_deadzone_raw:
                                        # 两个扳机都松开
                                        action[2] = 0.0
                                    else:
                                        # 左扳机还在使用，机械臂上升
                                        z_normalized = z_raw / 255.0
                                        action[2] = z_normalized * self.controller_config.scale['ABS_Z']
                                else:
                                    action[2] = 0.0
                            elif action[2] < -0.001:
                                # action[2]是负值，但右扳机可能已经松开，重置
                                action[2] = 0.0
                    
                    if 'ABS_Z' in axis_values and 'ABS_Z' in axis_last_update:
                        if current_time - axis_last_update['ABS_Z'] > axis_timeout:
                            z_raw = axis_values['ABS_Z']
                            # 如果左扳机松开（值接近0），或者action[2]是正值，则重置
                            if z_raw < trigger_deadzone_raw:
                                # 左扳机松开，检查右扳机状态
                                if 'ABS_RZ' in axis_values:
                                    rz_raw = axis_values['ABS_RZ']
                                    if rz_raw < trigger_deadzone_raw:
                                        # 两个扳机都松开
                                        action[2] = 0.0
                                    else:
                                        # 右扳机还在使用，机械臂下降
                                        rz_normalized = rz_raw / 255.0
                                        action[2] = -rz_normalized * self.controller_config.scale['ABS_RZ']
                                else:
                                    action[2] = 0.0
                            elif action[2] > 0.001:
                                # action[2]是正值，但左扳机可能已经松开，重置
                                action[2] = 0.0
                    
                    last_check_time = current_time
                
                # 如果没有事件，短暂休眠，避免CPU占用过高
                if not has_events:
                    time.sleep(0.01)
                
                # 每次循环都更新共享状态，即使没有新事件也保持当前状态
                # 使用copy()避免引用问题
                self.latest_data["action"] = action.copy()
                self.latest_data["buttons"] = buttons.copy()
                
            except inputs.UnpluggedError:
                # 手柄未连接，等待后重试
                print("未找到手柄，正在重试...")
                # 重置所有动作，避免使用旧数据
                action = [0.0] * 6
                buttons = [False, False]
                self.latest_data["action"] = action.copy()
                self.latest_data["buttons"] = buttons.copy()
                time.sleep(1)
            except Exception as e:
                # 其他错误，打印错误信息并短暂等待
                print(f"读取手柄时出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

    def get_action(self):
        """
        获取最新的动作和按钮状态
        
        Returns:
            Tuple[np.ndarray, list]:
                - action: 6DOF动作数组 [x, y, z, roll, pitch, yaw]
                - buttons: 按钮状态列表 [左扳机, 右扳机]
        """
        action = self.latest_data["action"]
        buttons = self.latest_data["buttons"]
        return np.array(action), buttons
    
    def close(self):
        """
        关闭手柄连接并终止后台进程
        """
        self.process.terminate()
