import sys
import tkinter as tk
from tkinter import scrolledtext
from tkinter.font import Font


class DebugWindow:
    def __init__(self, master):
        self.master = master
        master.title("调试窗口")
        master.geometry("700x540")

        # 创建工具栏
        self.toolbar = tk.Frame(master)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # 刷新按钮
        self.refresh_button = tk.Button(self.toolbar, text="刷新", command=self.refresh_text)
        self.refresh_button.pack(side=tk.LEFT, padx=2, pady=2)

        # 缩进复选框
        self.indent_var = tk.BooleanVar(value=True)
        self.indent_checkbox = tk.Checkbutton(self.toolbar, text="缩进", variable=self.indent_var, command=self.refresh_text)
        self.indent_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 调用复选框
        self.callstack_var = tk.BooleanVar(value=True)
        self.callstack_checkbox = tk.Checkbutton(self.toolbar, text="调用", variable=self.callstack_var, command=self.refresh_text)
        self.callstack_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 创建带滚动条的文本框
        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # 设置字体
        font = Font(family="monospace", size=10)
        self.text_area.config(font=font)

        # 初始化显示日志
        self.refresh_text()

    def refresh_text(self):
        """刷新文本区域，根据复选框的状态更新内容显示"""
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        logs = sys.stdout.get_logs()

        # 处理日志输出，不改变原始 logs 内容
        for log in logs:
            self.text_area.insert(tk.END, f"（{log}）")

        self.text_area.config(state=tk.DISABLED)


