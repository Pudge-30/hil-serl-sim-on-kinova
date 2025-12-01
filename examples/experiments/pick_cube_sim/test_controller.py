#!/usr/bin/env python3
"""
测试手柄连接与功能的程序
用于测试盖世小鸡启明星2无线手柄（或其他手柄）的连接和功能

使用方法:
    python test_controller.py --controller gamesir
    python test_controller.py --controller xbox
    python test_controller.py --controller ps5
"""

import argparse
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from franka_env.spacemouse.spacemouse_expert import JoystickExpert, ControllerType

def print_action_info(action, buttons, controller_type):
    """打印动作和按钮信息"""
    print("\r" + "=" * 80, end="")
    print(f"\n控制器类型: {controller_type.value.upper()}")
    print(f"动作值 (6DOF):")
    print(f"  X (前后):     {action[0]:8.4f}  ", end="")
    print("|" if abs(action[0]) > 0.01 else " ", end="")
    print(" " * int(abs(action[0]) * 20) + "●" if abs(action[0]) > 0.01 else "")
    print(f"  Y (左右):     {action[1]:8.4f}  ", end="")
    print("|" if abs(action[1]) > 0.01 else " ", end="")
    print(" " * int(abs(action[1]) * 20) + "●" if abs(action[1]) > 0.01 else "")
    print(f"  Z (上下):     {action[2]:8.4f}  ", end="")
    print("|" if abs(action[2]) > 0.01 else " ", end="")
    print(" " * int(abs(action[2]) * 20) + "●" if abs(action[2]) > 0.01 else "")
    print(f"  RX (旋转X):   {action[3]:8.4f}  ", end="")
    print("|" if abs(action[3]) > 0.01 else " ", end="")
    print(" " * int(abs(action[3]) * 20) + "●" if abs(action[3]) > 0.01 else "")
    print(f"  RY (旋转Y):   {action[4]:8.4f}  ", end="")
    print("|" if abs(action[4]) > 0.01 else " ", end="")
    print(" " * int(abs(action[4]) * 20) + "●" if abs(action[4]) > 0.01 else "")
    print(f"  RZ (旋转Z):   {action[5]:8.4f}  ", end="")
    print("|" if abs(action[5]) > 0.01 else " ", end="")
    print(" " * int(abs(action[5]) * 20) + "●" if abs(action[5]) > 0.01 else "")
    print(f"\n按钮状态:")
    print(f"  左扳机 (BTN_TL, 关闭夹爪): {'● 按下' if buttons[0] else '○ 未按下'}")
    print(f"  右扳机 (BTN_TR, 打开夹爪): {'● 按下' if buttons[1] else '○ 未按下'}")
    print(f"\n操作说明:")
    print(f"  - 左摇杆: 控制 X(前后) 和 Y(左右)")
    print(f"  - 右摇杆: 控制 RX(旋转X) 和 RY(旋转Y)")
    print(f"  - 扳机键: 控制 Z(上下)")
    print(f"  - 左扳机 (BTN_TL): 关闭夹爪")
    print(f"  - 右扳机 (BTN_TR): 打开夹爪")
    print(f"  - 按 Ctrl+C 退出")
    print("=" * 80, end="", flush=True)


def test_controller_raw_events():
    """测试原始手柄事件（用于调试）"""
    print("\n" + "=" * 80)
    print("原始事件模式 - 显示所有手柄输入事件")
    print("按 Ctrl+C 退出")
    print("=" * 80 + "\n")
    
    try:
        import inputs
        while True:
            try:
                events = inputs.get_gamepad()
                for event in events:
                    print(f"事件类型: {event.ev_type:8s} | 代码: {event.code:15s} | 状态: {event.state:10d}")
            except inputs.UnpluggedError:
                print("未检测到手柄，请检查连接...")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n退出原始事件模式")


def test_controller_mapping(controller_type):
    """测试手柄映射和功能"""
    print("\n" + "=" * 80)
    print(f"测试 {controller_type.value.upper()} 手柄连接与功能")
    print("=" * 80)
    print("\n正在初始化手柄...")
    
    try:
        expert = JoystickExpert(controller_type=controller_type)
        print("✓ 手柄初始化成功！\n")
        time.sleep(0.5)
        
        print("开始读取手柄输入...")
        print("请操作手柄的摇杆和按钮，观察输出变化\n")
        time.sleep(1)
        
        last_action = None
        last_buttons = None
        
        while True:
            action, buttons = expert.get_action()
            
            # 只在有变化时打印，减少输出
            if last_action is None or not (np.allclose(action, last_action, atol=0.01) and buttons == last_buttons):
                print_action_info(action, buttons, controller_type)
                last_action = action.copy()
                last_buttons = buttons.copy()
            
            time.sleep(0.05)  # 20Hz 更新频率
            
    except KeyboardInterrupt:
        print("\n\n正在关闭手柄连接...")
        expert.close()
        print("✓ 已退出")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        print("\n可能的原因:")
        print("  1. 手柄未连接或未正确识别")
        print("  2. 需要管理员权限（Linux 可能需要将用户添加到 input 组）")
        print("  3. 手柄驱动未正确安装")
        print("\n建议:")
        print("  - 运行 'python test_controller.py --raw' 查看原始事件")
        print("  - 检查 'lsusb' 或 'ls /dev/input/' 确认手柄被系统识别")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="测试手柄连接与功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试盖世小鸡启明星2无线手柄（默认）
  python test_controller.py --controller gamesir
  
  # 或直接运行（默认就是gamesir）
  python test_controller.py
  
  # 查看原始事件（用于调试）
  python test_controller.py --raw
        """
    )
    
    parser.add_argument(
        "--controller",
        type=str,
        default="gamesir",
        choices=["gamesir"],
        help="手柄类型 (默认: gamesir，仅支持盖世小鸡启明星2无线手柄)"
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="显示原始手柄事件（用于调试）"
    )
    
    args = parser.parse_args()
    
    if args.raw:
        test_controller_raw_events()
    else:
        # 将字符串转换为 ControllerType 枚举
        controller_map = {
            "gamesir": ControllerType.GAMESIR,
        }
        controller_type = controller_map[args.controller.lower()]
        test_controller_mapping(controller_type)


if __name__ == "__main__":
    import numpy as np
    main()
