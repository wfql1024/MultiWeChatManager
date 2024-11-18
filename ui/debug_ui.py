import sys
import tkinter as tk
from tkinter import scrolledtext
from tkinter.font import Font

from utils import debug_utils


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

        # 创建Frame用于包含两个滑块
        self.indent_frame = tk.Frame(self.toolbar)
        self.indent_frame.pack(side=tk.LEFT, padx=5, pady=2)

        # 最小缩进尺
        self.min_indent_label = tk.Label(self.indent_frame, text="最小缩进:")
        self.min_indent_label.pack(side=tk.LEFT)
        self.min_indent_scale = tk.Scale(self.indent_frame, from_=0, to=20, orient=tk.HORIZONTAL,
                                         command=lambda x: self.update_indent_scales())
        self.min_indent_scale.set(0)  # 设置默认最小缩进
        self.min_indent_scale.pack(side=tk.LEFT)

        # 最大缩进尺
        self.max_indent_label = tk.Label(self.indent_frame, text="最大缩进:")
        self.max_indent_label.pack(side=tk.LEFT)
        self.max_indent_scale = tk.Scale(self.indent_frame, from_=0, to=20, orient=tk.HORIZONTAL,
                                         command=lambda x: self.update_indent_scales())
        self.max_indent_scale.set(20)  # 设置默认最大缩进
        self.max_indent_scale.pack(side=tk.LEFT)

        # 调用复选框
        self.callstack_var = tk.BooleanVar(value=True)
        self.callstack_checkbox = tk.Checkbutton(self.toolbar, text="调用栈", variable=self.callstack_var,
                                                 command=self.update_simplify_checkbox)
        self.callstack_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 简化复选框
        self.simplify_var = tk.BooleanVar(value=True)
        self.simplify_checkbox = tk.Checkbutton(self.toolbar, text="简化调用栈",
                                                variable=self.simplify_var, command=self.refresh_text)
        self.simplify_checkbox.pack(side=tk.LEFT, padx=2, pady=2)

        # 创建带滚动条的文本框
        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.tag_configure("unimportant", foreground="grey")

        # 设置字体
        font = Font(family="JetBrains Mono", size=10)
        self.text_area.config(font=font)

        # 初始化显示日志
        self.refresh_text()

    # 更新缩进滑块逻辑
    def update_indent_scales(self):
        """缩进滑块的更新"""
        min_indent = self.min_indent_scale.get()
        max_indent = self.max_indent_scale.get()

        # 确保最小缩进小于最大缩进
        if min_indent > max_indent:
            self.min_indent_scale.set(max_indent)
            self.max_indent_scale.set(min_indent)

        # 调用refresh_text更新显示
        self.refresh_text()

    def update_simplify_checkbox(self):
        """刷新简化复选框"""
        if self.callstack_var.get():
            self.simplify_checkbox.config(state=tk.NORMAL)  # 启用
        else:
            self.simplify_checkbox.config(state=tk.DISABLED)  # 禁用
        self.refresh_text()

    def refresh_text(self):
        """刷新文本区域，根据复选框的状态更新内容显示"""
        self.text_area.config(state=tk.NORMAL)
        current_scroll_position = self.text_area.yview()  # 保存当前滚动位置
        self.text_area.delete(1.0, tk.END)

        logs = sys.stdout.get_logs()
        for log in logs:
            if len(log['output_prefix']) < self.min_indent_scale.get() or len(
                    log['output_prefix']) > self.max_indent_scale.get():
                continue
            # 调用栈前缀
            if self.indent_var.get() and self.callstack_var.get():
                stack_prefix = log['stack_prefix']
            else:
                stack_prefix = ""
            # 调用栈
            if self.callstack_var.get():
                if self.simplify_var.get() is False:
                    call_stack = log['call_stack'] + "\n"
                else:
                    origin_call_stack = log['call_stack']
                    call_stack = debug_utils.simplify_call_stack(origin_call_stack) + "\n"
            else:
                call_stack = ""
            # 输出前缀
            if self.indent_var.get():
                output_prefix = log['output_prefix']
            else:
                output_prefix = ""
            # 输出
            if self.callstack_var.get():
                output_content = log['output_content'] + "\n"
            else:
                output_content = log['output_content'] + "\n"

            self.text_area.insert(tk.END, stack_prefix, "unimportant")
            self.text_area.insert(tk.END, call_stack, "unimportant")
            self.text_area.insert(tk.END, output_prefix, "unimportant")
            self.text_area.insert(tk.END, output_content)

        self.text_area.update_idletasks()  # 确保插入文本后所有更新完成
        self.text_area.yview_moveto(current_scroll_position[0])  # 恢复滚动条位置

        self.text_area.config(state=tk.DISABLED)
