# ui_helper.py
import tkinter as tk
from io import BytesIO
from tkinter import ttk

import requests
from PIL import Image, ImageTk


class UIHelper:


    def create_dynamic_width_button(parent, text, command):
        # 创建一个临时的标签来计算文本宽度
        temp_label = tk.Label(parent, text=text)
        text_width = temp_label.winfo_reqwidth()

        # 删除临时标签
        temp_label.destroy()

        # 计算按钮宽度：文本宽度 + 一些额外空间(根据需要调整)
        button_width = text_width + 20  # 20是额外的像素，可以根据需要调整

        # 创建按钮
        button = ttk.Button(parent, text=text, command=command, width=button_width)
        return button

    @staticmethod
    def create_account_row(parent_frame, account, display_name, is_logged_in, config_status, callbacks, avatar_url):
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill=tk.X, pady=2)

        # 添加复选框
        checkbox_var = tk.BooleanVar()
        checkbox = ttk.Checkbutton(row_frame, variable=checkbox_var)
        checkbox.pack(side=tk.LEFT, padx=(0, 5), pady=(0, 0))

        # 添加头像
        try:
            response = requests.get(avatar_url)
            img = Image.open(BytesIO(response.content))
            img = img.resize((44, 44), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(row_frame, image=photo)
            avatar_label.image = photo  # 保持对图像的引用
        except Exception:
            # 如果加载失败，使用一个空白标签
            avatar_label = ttk.Label(row_frame, width=10)
        avatar_label.pack(side=tk.LEFT, padx=(0, 5), pady=(0, 0))

        account_label = ttk.Label(row_frame, text=display_name)
        account_label.pack(side=tk.LEFT, padx=(0, 10))

        button_frame = ttk.Frame(row_frame)
        button_frame.pack(side=tk.RIGHT)

        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        note_button = ttk.Button(button_frame, text="备注", style='Custom.TButton', width=4,
                                 command=lambda: callbacks['note'](account))
        note_button.pack(side=tk.RIGHT, padx=0)

        if is_logged_in:
            config_button_text = "重新配置" if config_status != "无配置" else "添加配置"
            config_button = ttk.Button(button_frame, text=config_button_text, style='Custom.TButton', width=8,
                                       command=lambda: callbacks['config'](account))
            config_button.pack(side=tk.RIGHT, padx=0)
        else:
            login_button = ttk.Button(button_frame, text="自动登录", style='Custom.TButton', width=8,
                                      command=lambda: callbacks['login'](account))
            login_button.pack(side=tk.RIGHT, padx=0)

            if config_status == "无配置":
                login_button.state(['disabled'])

        date_frame = ttk.Frame(row_frame)
        date_frame.pack(side=tk.RIGHT, padx=(10, 10), fill=tk.X, expand=True)

        config_status_label = ttk.Label(date_frame, text=config_status)
        config_status_label.pack(side=tk.RIGHT)

        ttk.Label(row_frame).pack(side=tk.LEFT, fill=tk.X, expand=True)
