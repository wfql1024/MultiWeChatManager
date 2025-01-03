import queue
import re
import sys
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import ttk

from resources import Constants
from utils import debug_utils
from utils.logger_utils import mylogger as logger


class ScrollableCanvas:
    def __init__(self, master_frame):
        self.master_frame = master_frame
        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        scrollbar_frame = tk.Frame(self.master_frame)
        scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.master_frame, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        print("创建滚动条...")
        self.scrollbar = ttk.Scrollbar(scrollbar_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        # 创建一个Frame在Canvas中
        self.main_frame = ttk.Frame(self.canvas)
        # 将main_frame放置到Canvas的窗口中，并禁用Canvas的宽高跟随调整
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        # 将滚动条连接到Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        # 配置Canvas的滚动区域
        self.canvas.bind('<Configure>', self.on_canvas_configure)

    def bind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", self.on_mousewheel, add='+')
        widget.bind("<Button-4>", self.on_mousewheel, add='+')
        widget.bind("<Button-5>", self.on_mousewheel, add='+')

        for child in widget.winfo_children():
            self.bind_mouse_wheel(child)

    def unbind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.unbind("<MouseWheel>")
        widget.unbind("<Button-4>")
        widget.unbind("<Button-5>")

        for child in widget.winfo_children():
            self.unbind_mouse_wheel(child)

    def on_mousewheel(self, event):
        """鼠标滚轮触发动作"""
        # 对于Windows和MacOS
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # 对于Linux
        else:
            if event.num == 5:
                self.canvas.yview_scroll(1, "units")
            elif event.num == 4:
                self.canvas.yview_scroll(-1, "units")

    def on_canvas_configure(self, event):
        """动态调整canvas中窗口的宽度，并根据父子间高度关系进行滚轮事件绑定与解绑"""
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            width = event.width
            self.canvas.itemconfig(tagOrId=self.canvas_window, width=width)
            if self.main_frame.winfo_height() > self.canvas.winfo_height():
                self.bind_mouse_wheel(self.canvas)
                self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
            else:
                self.unbind_mouse_wheel(self.canvas)
                self.scrollbar.pack_forget()
        except Exception as e:
            logger.error(e)


class StatusBar:
    def __init__(self, root, r_class, debug):

        self.status_bar = None
        self.statusbar_output_var = None

        self.root = root
        self.r_class = r_class
        self.debug = debug

        # 创建状态栏
        self.create_status_bar()
        self.message_queue = queue.Queue()  # 创建消息队列
        sys.stdout = debug_utils.RedirectText(self.statusbar_output_var, self.message_queue, self.debug)  # 重定向 stdout
        self.update_status()  # 定期检查队列中的消息

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏...")
        self.statusbar_output_var = tk.StringVar()
        self.status_bar = tk.Label(self.root, textvariable=self.statusbar_output_var, bd=Constants.STATUS_BAR_BD,
                                   relief=tk.SUNKEN, anchor=tk.W, height=Constants.STATUS_BAR_HEIGHT)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # 绑定点击事件
        if self.debug:
            self.status_bar.bind("<Button-1>", lambda event: self.r_class.open_debug_window())

    def update_status(self):
        """即时更新状态栏"""
        try:
            # 从队列中获取消息并更新状态栏
            message = self.message_queue.get_nowait()
            if message.strip():  # 如果消息不为空，更新状态栏
                self.statusbar_output_var.set(message)
        except queue.Empty:
            pass
        except Exception as e:
            print(e)
            pass
        # 每 1 毫秒检查一次队列
        self.root.after(1, self.update_status)


class UnlimitedClickHandler:
    def __init__(self, root, widget, *funcs):
        """
        初始化 ClickHandler 类，接收 root 和外部提供的点击处理函数。

        :param root: 主窗口对象
        :param widget: 要绑定事件的 Tkinter 小部件
        :param funcs: 任意数量的点击事件处理函数，从单击到 n 击
        """
        self.root = root
        self.widget = widget
        self.funcs = funcs  # 点击事件的处理函数列表，这些都还没有传入event
        self.click_count = 0  # 记录点击次数
        self.single_click_id = None

        # 绑定单击事件
        widget.bind("<Button-1>", self.on_click)

    def on_click(self, event=None):
        """处理点击事件（单击、双击、三击等）"""
        self.click_count += 1  # 增加点击次数
        # print(f"点击了控件：{event.widget}")

        # 取消之前的延时处理（如果有）
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)

        # 设置一个延时，等待是否有更多的点击
        self.single_click_id = self.root.after(200, self.handle_click, event)

    def handle_click(self, event=None):
        """根据点击次数调用对应的处理函数"""
        click_count = self.click_count
        # print("重置次数")
        self.click_count = 0
        if click_count <= len(self.funcs):
            # 如果点击次数在函数范围内，调用对应的函数
            print(f"用户{click_count}击")
            # 使用 partial 创建新的函数并等待延时执行
            partial(self.funcs[click_count - 1], event=event)()
        else:
            # 如果点击次数超出定义的函数范围，调用最后一个函数
            print(f"用户{click_count}击，实际触发{len(self.funcs)}击")
            # 使用 partial 创建新的函数并等待延时执行
            partial(self.funcs[-1], event=event)()


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() - 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def hide(self, _event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def add_hyperlink_events(text_widget, text_content):
    """为文本框中的URL添加点击事件，并在鼠标移动到链接时变成手型"""

    def open_url(url_to_open):
        if url_to_open is None or url_to_open == "":
            return
        webbrowser.open_new(url_to_open)

    urls = re.findall(r'(https?://\S+)', text_content)  # 使用正则表达式提取URL
    for url in urls:
        start_idx = text_widget.search(url, "1.0", tk.END)
        end_idx = f"{start_idx}+{len(url)}c"

        # 为找到的URL添加标签，并绑定事件
        text_widget.tag_add(url, start_idx, end_idx)
        text_widget.tag_config(url, foreground="grey", underline=True)

        # 鼠标点击事件 - 打开链接
        text_widget.tag_bind(url, "<Button-1>", lambda e, url2open=url: open_url(url2open))

        # 鼠标进入事件 - 改变鼠标形状为手型
        text_widget.tag_bind(url, "<Enter>", lambda e: text_widget.config(cursor="hand2"))

        # 鼠标离开事件 - 恢复鼠标形状为默认
        text_widget.tag_bind(url, "<Leave>", lambda e: text_widget.config(cursor=""))


def auto_scroll_text(tasks, direction_key, text_widget, root, gap=50, scroll_distance=0.005):
    """每秒滚动一行，保持滚动方向一致"""
    # 获取当前视图的最大滚动位置（即文本框的底部）
    top_pos = text_widget.yview()[0]
    bottom_pos = text_widget.yview()[1]
    max_pos = 1.0

    # 确保方向状态从外部获取
    direction = getattr(direction_key, "value", 1)  # 默认向下
    # print(direction)

    pause = 0
    if bottom_pos >= max_pos:
        direction = -1  # 改为向上
        pause = 1000
    elif top_pos <= 0:
        direction = 1  # 改为向下
        pause = 1000

    # 更新滚动方向到外部变量
    setattr(direction_key, "value", direction)

    # 根据方向计算目标位置
    target_pos = top_pos + scroll_distance * direction
    text_widget.yview_moveto(target_pos)

    # 添加任务并返回
    scroll_task = root.after(
        gap + pause,
        lambda: auto_scroll_text(tasks, direction_key, text_widget, root, gap, scroll_distance)
    )
    tasks.append(scroll_task)


def insert_two_lines(text_widget, line_list):
    """在Text中插入每行两个元素，并且居中显示"""
    for i in range(0, len(line_list), 2):  # 每两个元素作为一对
        left_text = line_list[i]
        right_text = line_list[i + 1] if i + 1 < len(line_list) else ""

        # 插入内容到Text
        text_widget.insert(tk.END, left_text)

        # 为右边部分添加标签，设置右对齐
        text_widget.insert(tk.END, " " * 10)  # 可以通过控制空格数来控制两个部分之间的间距
        text_widget.insert(tk.END, right_text + "\n")  # 插入右边部分

    # 更新Text视图
    text_widget.see(tk.END)  # 确保插入的文本可以显示在视图中


def disable_button_and_add_tip(tooltips, button, text):
    """
    禁用按钮，启用提示
    :return: None
    """
    button.state(['disabled'])
    if button not in tooltips:
        tooltips[button] = Tooltip(button, text)


def enable_button_and_unbind_tip(tooltips, button):
    """
    启用按钮，去除提示
    :return: None
    """
    button.state(['!disabled'])
    if button in tooltips:
        tooltips[button].widget.unbind("<Enter>")
        tooltips[button].widget.unbind("<Leave>")
        del tooltips[button]


def remove_a_tag_of_item(tree, item_id, tag_to_remove):
    current_tags = tree.item(item_id, "tags")
    if isinstance(current_tags, str) and current_tags == "":
        current_tags = ()  # 将空字符串转换为元组
    new_tags = tuple(tag for tag in current_tags if tag != tag_to_remove)
    tree.item(item_id, tags=list(new_tags))
    # print(current_tags, new_tags, tree.item(item_id, "tags"))


def add_a_tag_to_item(tree, item_id, tag_to_add):
    current_tags = tree.item(item_id, "tags")
    if isinstance(current_tags, str) and current_tags == "":
        current_tags = ()  # 将空字符串转换为元组
    new_tags = current_tags + (tag_to_add,)
    tree.item(item_id, tags=list(new_tags))
    # print(current_tags, new_tags, tree.item(item_id, "tags"))
