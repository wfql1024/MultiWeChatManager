# rewards_ui.py
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from utils import hwnd_utils


class RewardsWindow:
    def __init__(self, root, parent, wnd, image_path):
        self.root = root
        self.parent = parent
        self.wnd = wnd
        self.wnd.title("我来赏你！")

        # 加载图片
        img = Image.open(image_path)
        # 设置窗口大小为图片的大小
        img_width, img_height = img.size  # 获取图片的宽和高
        hwnd_utils.bring_wnd_to_center(self.wnd, img_width, img_height)

        # 移除窗口装饰并设置为工具窗口
        wnd.attributes('-toolwindow', True)

        # 创建Frame并填充
        frame = ttk.Frame(wnd)
        frame.pack(fill=tk.BOTH, expand=True)

        # 调用方法在frame中显示图片
        self.show_image_in_frame(frame, img)

    @staticmethod
    def show_image_in_frame(frame, img):
        # 将图片转换为Tkinter格式
        tk_img = ImageTk.PhotoImage(img)

        # 在frame中创建Label用于显示图片
        label = ttk.Label(frame, image=tk_img)
        label.image = tk_img  # 防止图片被垃圾回收
        label.pack()


# 创建Tkinter应用窗口
if __name__ == "__main__":
    # root = tk.Tk()
    # img_path = 'path_to_your_image.png'  # 替换为你的图片路径
    # app = RewardsWindow(root, root, root, img_path)
    # root.mainloop()
    pass
