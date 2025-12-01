import mujoco.viewer

class DualMujocoViewer:
    def __init__(
            self,
            model,
            data,
            key_callback=None
    ):
        self.model = model
        self.data = data
        self.viewer_1 = None
        self.viewer_2 = None
        self.key_callback = key_callback

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def launch(self):
        self.viewer_1 = mujoco.viewer.launch_passive(
            self.model,
            self.data,
            show_left_ui=False,
            show_right_ui=False,
            key_callback=self.key_callback
        )
        # self.viewer_2 = mujoco.viewer.launch_passive(
        #     self.model,
        #     self.data,
        #     show_left_ui=False,
        #     show_right_ui=False,
        #     key_callback=self.key_callback
        # )

    def is_running(self):
        # return self.viewer_1.is_running() and self.viewer_2.is_running()
        return self.viewer_1.is_running()

    def sync(self):
        if self.viewer_1:
            self.viewer_1.sync()
        # if self.viewer_2:
        #     self.viewer_2.sync()

    def close(self):
        """
        关闭viewer并清理资源
        
        注意：MuJoCo viewer的close()方法应该已经处理了GLFW资源的清理。
        我们不应该手动调用glfw.terminate()，因为这可能会影响其他使用GLFW的代码。
        """
        try:
            if self.viewer_1:
                self.viewer_1.close()
                self.viewer_1 = None
            # if self.viewer_2:
            #     self.viewer_2.close()
            #     self.viewer_2 = None
        except Exception as e:
            print(f"关闭viewer时出现警告: {e}")
        
        # 不再手动调用glfw.terminate()
        # MuJoCo viewer的close()方法应该已经处理了GLFW资源的清理
        # 手动调用glfw.terminate()会导致后续使用GLFW的操作失败（如环境重置等）
