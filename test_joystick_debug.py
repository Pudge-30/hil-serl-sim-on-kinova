"""
手柄调试脚本 - 增强版

用于诊断手柄输入问题，显示：
1. 原始手柄事件值
2. 归一化后的值
3. 缩放后的最终动作值
4. 各轴的映射关系
5. 摇杆输入值的取值范围（最大值和最小值）

使用方法：
    python test_joystick_debug.py              # 显示处理后的动作值
    python test_joystick_debug.py --raw        # 显示原始输入事件
    python test_joystick_debug.py --range      # 监测摇杆取值范围
"""
import time
import numpy as np
import inputs
from serl_robot_infra.franka_env.spacemouse.spacemouse_expert import JoystickExpert, ControllerType

def test_raw_inputs():
    """测试原始输入，显示所有手柄事件"""
    print("\n" + "=" * 80)
    print("原始输入测试 - 显示所有手柄事件（按Ctrl+C退出）")
    print("=" * 80)
    print(f"{'事件代码':<15} {'原始值':<15} {'事件类型':<15}")
    print("-" * 80)
    
    try:
        while True:
            events = inputs.get_gamepad()
            for event in events:
                print(f"{event.code:<15} {event.state:<15} {event.ev_type:<15}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n停止原始输入测试")

def test_processed_inputs():
    """测试处理后的输入"""
    print("\n初始化手柄...")
    # 仅支持盖世小鸡手柄
    controller_types = [ControllerType.GAMESIR]
    
    expert = None
    controller_type = None
    for ctype in controller_types:
        try:
            print(f"尝试连接 {ctype.value} 手柄...")
            expert = JoystickExpert(controller_type=ctype)
            time.sleep(0.5)  # 等待初始化
            action, buttons = expert.get_action()
            print(f"成功连接到 {ctype.value} 手柄")
            controller_type = ctype
            break
        except Exception as e:
            print(f"无法连接 {ctype.value} 手柄: {e}")
            if expert:
                expert.close()
            expert = None
    
    if expert is None:
        print("无法连接到任何手柄！")
        return None, None
    
    # 显示配置信息
    config = expert.controller_config
    print(f"\n手柄配置信息:")
    print(f"  类型: {controller_type.value}")
    print(f"  分辨率配置: {config.resolution}")
    print(f"  缩放因子配置: {config.scale}")
    print(f"\n轴映射关系:")
    print(f"  ABS_Y (左摇杆Y) -> action[0] (Y轴平移)")
    print(f"  ABS_X (左摇杆X) -> action[1] (X轴平移)")
    print(f"  ABS_RZ (右扳机) -> action[2] (Z轴平移, 向上)")
    print(f"  ABS_Z (左扳机) -> action[2] (Z轴平移, 向下)")
    print(f"  ABS_RX (右摇杆X) -> action[3] (Roll旋转)")
    print(f"  ABS_RY (右摇杆Y) -> action[4] (Pitch旋转)")
    print(f"  ABS_HAT0X (D-pad) -> action[5] (Yaw旋转)")
    print(f"\n注意:")
    print(f"  - 系统会自动检测每个轴的值范围（有符号/无符号）")
    print(f"  - 如果看到负值，将使用有符号归一化（中心值=0）")
    print(f"  - 如果只看到正值，将使用无符号归一化（中心值=分辨率/2）")
    
    return expert, controller_type

def test_range_detection(duration=30):
    """
    监测摇杆输入值的取值范围
    
    Args:
        duration: 监测时长（秒），默认30秒
    """
    print("\n" + "=" * 100)
    print(f"摇杆取值范围监测 - 将监测 {duration} 秒（按Ctrl+C可提前退出）")
    print("=" * 100)
    print("\n请操作手柄的所有摇杆和扳机，尽量推到各个方向的极限位置")
    print("这将帮助我们确定每个轴的实际取值范围\n")
    
    # 存储每个轴的最小值和最大值
    axis_min = {}
    axis_max = {}
    axis_count = {}  # 记录每个轴的事件数量
    axis_sum = {}  # 记录每个轴的值总和（用于计算平均值）
    axis_first_value = {}  # 记录每个轴的第一个值
    axis_last_value = {}  # 记录每个轴的最后一个值
    
    # 需要监测的轴
    monitored_axes = ['ABS_X', 'ABS_Y', 'ABS_RX', 'ABS_RY', 'ABS_Z', 'ABS_RZ', 'ABS_HAT0X']
    
    start_time = time.time()
    last_print_time = start_time
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 检查是否超过指定时长
            if elapsed >= duration:
                break
            
            # 获取手柄事件
            events = inputs.get_gamepad()
            
            for event in events:
                if event.ev_type == 'Absolute' and event.code in monitored_axes:
                    code = event.code
                    value = event.state
                    
                    # 初始化或更新最小值和最大值
                    if code not in axis_min:
                        axis_min[code] = value
                        axis_max[code] = value
                        axis_count[code] = 1
                        axis_sum[code] = value
                        axis_first_value[code] = value
                    else:
                        axis_min[code] = min(axis_min[code], value)
                        axis_max[code] = max(axis_max[code], value)
                        axis_count[code] += 1
                        axis_sum[code] += value
                    
                    axis_last_value[code] = value
            
            # 每2秒更新一次显示
            if current_time - last_print_time >= 2.0:
                remaining = duration - elapsed
                print(f"\r已监测 {elapsed:.1f} 秒，剩余 {remaining:.1f} 秒...", end="", flush=True)
                last_print_time = current_time
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n\n用户中断监测")
    
    # 显示结果
    print("\n\n" + "=" * 120)
    print("监测结果 - 每个轴的取值范围")
    print("=" * 120)
    print(f"{'轴代码':<12} {'最小值':<12} {'最大值':<12} {'范围':<12} {'平均值':<12} {'事件数':<10} {'中心估计':<12} {'类型判断':<20}")
    print("-" * 120)
    
    for axis in monitored_axes:
        if axis in axis_min:
            min_val = axis_min[axis]
            max_val = axis_max[axis]
            range_val = max_val - min_val
            count = axis_count[axis]
            avg_val = axis_sum[axis] / count if count > 0 else 0
            first_val = axis_first_value[axis]
            last_val = axis_last_value[axis]
            
            # 判断类型和中心值
            if min_val < 0:
                axis_type = "有符号 (signed)"
                center_estimate = 0
            elif max_val > 40000:
                axis_type = "无符号 (unsigned)"
                center_estimate = (min_val + max_val) / 2
            else:
                # 根据值范围和平均值判断
                # 如果平均值接近0，可能是有符号
                # 如果平均值接近范围中点，可能是无符号
                range_mid = (min_val + max_val) / 2
                if abs(avg_val) < abs(range_mid) * 0.3:  # 平均值更接近0
                    axis_type = "可能是有符号"
                    center_estimate = 0
                else:
                    axis_type = "可能是无符号"
                    center_estimate = range_mid
            
            print(f"{axis:<12} {min_val:<12} {max_val:<12} {range_val:<12} {avg_val:<12.1f} {count:<10} {center_estimate:<12.1f} {axis_type:<20}")
        else:
            print(f"{axis:<12} {'未检测到数据':<12}")
    
    print("\n" + "=" * 120)
    print("详细分析建议：")
    print("=" * 120)
    
    for axis in monitored_axes:
        if axis in axis_min:
            min_val = axis_min[axis]
            max_val = axis_max[axis]
            avg_val = axis_sum[axis] / axis_count[axis] if axis_count[axis] > 0 else 0
            range_mid = (min_val + max_val) / 2
            
            print(f"\n【{axis}】")
            print(f"  值范围: [{min_val}, {max_val}]")
            print(f"  范围大小: {max_val - min_val}")
            print(f"  平均值: {avg_val:.1f}")
            print(f"  事件数: {axis_count[axis]}")
            
            if min_val < 0:
                print(f"  ✓ 检测到负值，确定使用有符号归一化")
                print(f"  → 归一化公式: normalized = raw_value / 32768.0")
                print(f"  → 中心值: 0")
                print(f"  → 摇杆推到最大时，normalized ≈ {max_val / 32768.0:.4f}")
                print(f"  → 摇杆推到最小时，normalized ≈ {min_val / 32768.0:.4f}")
            elif max_val > 40000:
                center = (min_val + max_val) / 2
                print(f"  ✓ 最大值很大 ({max_val})，确定使用无符号归一化")
                print(f"  → 归一化公式: normalized = (raw_value - {center:.1f}) / {center:.1f}")
                print(f"  → 中心值: {center:.1f}")
                print(f"  → 摇杆推到最大时，normalized ≈ {((max_val - center) / center):.4f}")
                print(f"  → 摇杆推到最小时，normalized ≈ {((min_val - center) / center):.4f}")
            else:
                print(f"  ? 值范围不确定，需要进一步判断")
                print(f"  → 如果中心值接近0（平均值接近0），使用有符号归一化")
                print(f"  → 如果中心值接近 {range_mid:.0f}（平均值接近范围中点），使用无符号归一化")
                print(f"  → 当前平均值: {avg_val:.1f}，范围中点: {range_mid:.1f}")
                if abs(avg_val) < abs(range_mid) * 0.3:
                    print(f"  → 建议: 使用有符号归一化（平均值更接近0）")
                else:
                    print(f"  → 建议: 使用无符号归一化（平均值更接近范围中点）")
    
    print("\n" + "=" * 120)
    print("使用建议：")
    print("=" * 120)
    print("1. 根据上述分析，确认每个轴的归一化模式（有符号/无符号）")
    print("2. 如果发现某个轴的归一化模式不正确，可以调整代码中的检测逻辑")
    print("3. 建议在操作手柄时，尽量将摇杆推到各个方向的极限位置")
    print("4. 如果某些轴没有数据，可能是因为该轴没有移动或未连接")
    print("=" * 120)

def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="手柄调试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 显示处理后的动作值
  python test_joystick_debug.py
  
  # 显示原始输入事件
  python test_joystick_debug.py --raw
  
  # 监测摇杆取值范围（默认30秒）
  python test_joystick_debug.py --range
  
  # 监测摇杆取值范围（自定义时长，如60秒）
  python test_joystick_debug.py --range --duration 60
        """
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="显示原始手柄事件（用于调试）"
    )
    
    parser.add_argument(
        "--range",
        action="store_true",
        help="监测摇杆输入值的取值范围（最大值和最小值）"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="监测时长（秒），仅在 --range 模式下有效（默认: 30）"
    )
    
    args = parser.parse_args()
    
    # 处理 --raw 参数
    if args.raw:
        test_raw_inputs()
        return
    
    # 处理 --range 参数
    if args.range:
        test_range_detection(duration=args.duration)
        return
    
    # 默认模式：显示处理后的动作值
    expert, controller_type = test_processed_inputs()
    if expert is None:
        return
    
    print("\n" + "=" * 100)
    print("处理后的输入测试 - 显示最终动作值（按Ctrl+C退出）")
    print("=" * 100)
    print(f"{'时间':<10} {'action[0]':<12} {'action[1]':<12} {'action[2]':<12} {'action[3]':<12} {'action[4]':<12} {'action[5]':<12} {'按钮':<10} {'模长':<10}")
    print("-" * 100)
    
    try:
        last_action = None
        while True:
            action, buttons = expert.get_action()
            norm = np.linalg.norm(action)
            time_str = time.strftime("%H:%M:%S")
            buttons_str = ", ".join([str(int(b)) for b in buttons])
            
            # 检查是否有变化
            changed = last_action is None or not np.allclose(action, last_action, atol=0.001)
            
            if changed or norm > 0.01:
                print(f"{time_str:<10} "
                      f"{action[0]:>11.4f} "
                      f"{action[1]:>11.4f} "
                      f"{action[2]:>11.4f} "
                      f"{action[3]:>11.4f} "
                      f"{action[4]:>11.4f} "
                      f"{action[5]:>11.4f} "
                      f"{buttons_str:<10} "
                      f"{norm:>9.4f} {'*' if norm > 0.01 else ''}")
                last_action = action.copy()
            
            time.sleep(0.05)  # 50ms更新一次
            
    except KeyboardInterrupt:
        print("\n\n停止读取")
    finally:
        expert.close()
        print("手柄连接已关闭")
    
    print("\n提示:")
    print("  - 使用 --raw 参数可以查看原始输入事件")
    print("  - 使用 --range 参数可以监测摇杆取值范围")
    print("  - 使用 --range --duration 60 可以自定义监测时长（秒）")

if __name__ == "__main__":
    main()
