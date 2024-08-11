# ui_helper.py
import tkinter as tk
from tkinter import ttk


class UIHelper:
    @staticmethod
    def center_window(window):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    @staticmethod
    def create_account_row(parent_frame, account, display_name, is_logged_in, config_status, callbacks):
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill=tk.X, pady=2)

        account_label = ttk.Label(row_frame, text=display_name)
        account_label.pack(side=tk.LEFT, padx=(0, 10))

        button_frame = ttk.Frame(row_frame)
        button_frame.pack(side=tk.RIGHT)

        note_button = ttk.Button(button_frame, text="备注", command=lambda: callbacks['note'](account))
        note_button.pack(side=tk.RIGHT, padx=(0, 5))

        if is_logged_in:
            config_button_text = "重新配置" if config_status != "无配置" else "配置"
            config_button = ttk.Button(button_frame, text=config_button_text,
                                       command=lambda: callbacks['config'](account))
            config_button.pack(side=tk.RIGHT, padx=(0, 5))
        else:
            login_button = ttk.Button(button_frame, text="自动登录",
                                      command=lambda: callbacks['login'](account))
            login_button.pack(side=tk.RIGHT, padx=(0, 5))

            if config_status == "无配置":
                login_button.state(['disabled'])

        date_frame = ttk.Frame(row_frame)
        date_frame.pack(side=tk.RIGHT, padx=(10, 10), fill=tk.X, expand=True)

        config_status_label = ttk.Label(date_frame, text=config_status)
        config_status_label.pack(side=tk.RIGHT)

        ttk.Label(row_frame).pack(side=tk.LEFT, fill=tk.X, expand=True)
