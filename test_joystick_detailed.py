"""
详细的手柄调试脚本

显示每个轴的：
1. 原始值
2. 配置的分辨率
3. 计算的中心值
4. 归一化后的值
5. 死区检查结果
6. 缩放后的最终值
"""
import time
import inputs
from serl_robot_infra.franka_env.spacemouse.spacemouse_expert import JoystickExpert, ControllerType

def analyze_event(event, controller_type):
    """分析单个事件，显示所有处理步骤"""
    expert = JoystickExpert(controller_type=controller_type)
    config = expert.controller_config
    expert.close()
    
    if event.code not in config.resolution:
        return None
    
    resolution = config.resolution[event.code]
    scale = config.scale[event.code]
    center = resolution / 2
    raw_value = event.state
    
    # 归一化
    normalized = (raw_value - center) / center
    
    # 死区检查
    deadzone = 0.05
    is_in_deadzone = abs(normalized) < deadzone
    normalized_after_deadzone = 0.0 if is_in_deadzone else normalized
    
    # 缩放
    scaled = normalized_after_deadzone * scale
    
    return {
        'code': event.code,
        'raw': raw_value,
        'resolution': resolution,
        'center': center,
        'normalized': normalized,
        'deadzone': deadzone,
        'is_in_deadzone': is_in_deadzone,
        'normalized_after_deadzone': normalized_after_deadzone,
        'scale': scale,
        'scaled': scaled,
    }

def main():
    print("=" * 100)
    print("详细手柄调试 - 显示每个事件的处理过程")
    print("=" * 100)
    print("\n请操作手柄的摇杆和按钮...")
    print("按 Ctrl+C 退出\n")
    
    # 仅支持盖世小鸡手柄
    controller_type = ControllerType.GAMESIR
    
    print(f"\n使用配置: {controller_type.value}")
    print("=" * 100)
    print(f"{'事件代码':<15} {'原始值':<12} {'分辨率':<12} {'中心值':<12} {'归一化':<12} {'死区':<8} {'缩放':<12} {'最终值':<12}")
    print("-" * 100)
    
    try:
        while True:
            events = inputs.get_gamepad()
            for event in events:
                if event.ev_type == 'Absolute':  # 只处理绝对轴事件
                    result = analyze_event(event, controller_type)
                    if result:
                        deadzone_str = "是" if result['is_in_deadzone'] else "否"
                        print(f"{result['code']:<15} "
                              f"{result['raw']:<12} "
                              f"{result['resolution']:<12.1f} "
                              f"{result['center']:<12.1f} "
                              f"{result['normalized']:<12.4f} "
                              f"{deadzone_str:<8} "
                              f"{result['scale']:<12.4f} "
                              f"{result['scaled']:<12.4f}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\n停止调试")

if __name__ == "__main__":
    main()
