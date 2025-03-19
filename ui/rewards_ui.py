# rewards_ui.py
import tkinter as tk
from abc import ABC
from tkinter import ttk

from PIL import Image, ImageTk

from public_class.reusable_widgets import SubToolWnd


class RewardsWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, image_path):
        self.img = None
        self.image_path = image_path

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        # 加载图片
        self.img = Image.open(self.image_path)
        # 设置窗口大小为图片的大小
        self.wnd_width, self.wnd_height = self.img.size

    def load_content(self):
        # 创建Frame并填充
        frame = ttk.Frame(self.wnd)
        frame.pack(fill=tk.BOTH, expand=True)
        # 调用方法在frame中显示图片
        self.show_image_in_frame(frame, self.img)

    @staticmethod
    def show_image_in_frame(frame, img):
        # 将图片转换为Tkinter格式
        tk_img = ImageTk.PhotoImage(img)

        # 在frame中创建Label用于显示图片
        label = ttk.Label(frame, image=tk_img)
        label.image = tk_img  # 防止图片被垃圾回收
        label.pack()
