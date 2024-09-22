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
        self.indent_checkbox = tk.Checkbutton(self.toolbar, text="缩进", variable=self.indent_var,
                                              command=self.refresh_text)
        self.indent_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 调用复选框
        self.callstack_var = tk.BooleanVar(value=True)
        self.callstack_checkbox = tk.Checkbutton(self.toolbar, text="调用", variable=self.callstack_var,
                                                 command=self.refresh_text)
        self.callstack_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 创建带滚动条的文本框
        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # 设置字体
        font = Font(family="monospace", size=9)
        self.text_area.config(font=font)

        # 初始化显示日志
        self.refresh_text()

    def refresh_text(self):
        """刷新文本区域，根据复选框的状态更新内容显示"""
        self.text_area.config(state=tk.NORMAL)
        current_scroll_position = self.text_area.yview()  # 保存当前滚动位置
        self.text_area.delete(1.0, tk.END)

        logs = sys.stdout.get_logs()

        # 处理日志输出，不改变原始 logs 内容
        for log in logs:
            # 根据用户条件，设置输出格式
            if self.indent_var.get() and self.callstack_var.get():
                stack_prefix = log['stack_prefix']
            else:
                stack_prefix = ""

            if self.callstack_var.get():
                call_stack = log['call_stack']
            else:
                call_stack = ""

            if self.indent_var.get():
                output_prefix = log['output_prefix']
            else:
                output_prefix = ""

            output_content = log['output_content']
            output_line = f"{stack_prefix}{call_stack}{output_prefix}{output_content}\n"

            self.text_area.insert(tk.END, output_line)

        self.text_area.update_idletasks()  # 确保插入文本后所有更新完成
        self.text_area.yview_moveto(current_scroll_position[0])  # 恢复滚动条位置

        self.text_area.config(state=tk.DISABLED)
