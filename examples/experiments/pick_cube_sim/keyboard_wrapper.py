import gymnasium as gym
import numpy as np
import threading
from pynput import keyboard

"""
Keyboard Controls for Franka Arm:

Position Control (Cartesian):
  W / S : Move Forward / Backward (+X / -X)
  A / D : Move Left / Right (+Y / -Y)
  Q / E : Move Up / Down (+Z / -Z)

Rotation Control (Euler Angles):
  I / K : Rotate around X-axis (+Rx / -Rx)
  J / L : Rotate around Y-axis (+Ry / -Ry)
  U / O : Rotate around Z-axis (+Rz / -Rz)

Gripper Control:
  Z : Toggle Gripper Open/Close

Usage:
  Pressing any of the above keys overrides the policy action.
  Releasing the key stops the movement on that axis.
  Gripper state toggles on each press of 'Z'.
"""

class KeyboardIntervention(gym.ActionWrapper):
    def __init__(self, env):
        super().__init__(env)
        self.current_action = np.zeros(7)  # [x, y, z, rx, ry, rz, gripper]
        self.intervened = False
        self.gripper_state = 1.0 # 1.0 for open, -1.0 for close
        
        # 键盘映射速度
        self.pos_speed = 0.5
        self.rot_speed = 0.5
        
        # 启动键盘监听线程
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.listener.start()

    def on_press(self, key):
        try:
            if hasattr(key, 'char'):
                if key.char == 'w': self.current_action[0] = self.pos_speed  # +x
                elif key.char == 's': self.current_action[0] = -self.pos_speed # -x
                elif key.char == 'a': self.current_action[1] = self.pos_speed  # +y
                elif key.char == 'd': self.current_action[1] = -self.pos_speed # -y
                elif key.char == 'q': self.current_action[2] = self.pos_speed  # +z
                elif key.char == 'e': self.current_action[2] = -self.pos_speed # -z
                
                elif key.char == 'i': self.current_action[3] = self.rot_speed  # +rx
                elif key.char == 'k': self.current_action[3] = -self.rot_speed # -rx
                elif key.char == 'j': self.current_action[4] = self.rot_speed  # +ry
                elif key.char == 'l': self.current_action[4] = -self.rot_speed # -ry
                elif key.char == 'u': self.current_action[5] = self.rot_speed  # +rz
                elif key.char == 'o': self.current_action[5] = -self.rot_speed # -rz
                
                elif key.char == 'z': # Toggle Gripper
                    self.gripper_state *= -1.0
                    self.current_action[6] = self.gripper_state

                # 只要有按键按下，就标记为干预状态
                self.intervened = True
            
        except AttributeError:
            pass

    def on_release(self, key):
        # 释放按键时重置对应轴的速度
        try:
            if hasattr(key, 'char'):
                if key.char in ['w', 's']: self.current_action[0] = 0
                elif key.char in ['a', 'd']: self.current_action[1] = 0
                elif key.char in ['q', 'e']: self.current_action[2] = 0
                elif key.char in ['i', 'k']: self.current_action[3] = 0
                elif key.char in ['j', 'l']: self.current_action[4] = 0
                elif key.char in ['u', 'o']: self.current_action[5] = 0
            
            # 如果所有动作轴都归零，则认为干预结束
            if np.all(self.current_action[:6] == 0):
                self.intervened = False
                
        except AttributeError:
            pass

    def action(self, action: np.ndarray) -> np.ndarray:
        if self.intervened:
            # 如果正在干预，返回键盘控制的动作
            # 保持当前的夹爪状态
            self.current_action[6] = self.gripper_state
            return self.current_action, True
        
        return action, False

    def step(self, action):
        new_action, replaced = self.action(action)
        obs, rew, done, truncated, info = self.env.step(new_action)
        
        if replaced:
            info["intervene_action"] = new_action
            
        return obs, rew, done, truncated, info
    
    def close(self):
        self.listener.stop()
        return super().close()

