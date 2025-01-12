import re
import tkinter as tk
import webbrowser
from functools import partial


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
            # print(f"用户{click_count}击")
            partial(self.funcs[click_count - 1], event=event)()
        else:
            # 如果点击次数超出定义的函数范围，调用最后一个函数
            # print(f"用户{click_count}击，实际触发{len(self.funcs)}击")
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


def enable_widget_with_condition(widget, condition):
    """
    根据条件动态启用控件。

    Args:
        widget: 需要设置状态的 tkinter 控件。
        condition: 一个元组，形式为 (数值, (最小允许值, 最大允许值))。
                   - 数值: 用于判断的当前值。
                   - 最小允许值: 若为 None，则不限制最小值。
                   - 最大允许值: 若为 None，则不限制最大值。

    操作:
        如果数值满足条件范围，则将控件设置为 "normal"；
        否则设置为 "disabled"。
    """
    # 解包 condition
    value, (min_value, max_value) = condition

    # 检查条件
    is_valid = True
    if min_value is not None:
        is_valid = is_valid and (value >= min_value)
    if max_value is not None:
        is_valid = is_valid and (value <= max_value)

    # 设置控件状态
    if is_valid:
        widget.config(state="normal")
    else:
        widget.config(state="disabled")


def set_widget_tip_with_condition(tooltips, widget, text, condition=None):
    """
    根据条件动态绑定或解绑控件的提示信息 (tooltip)。

    Args:
        tooltips (dict): 存储 widget 和对应 Tooltip 实例的字典。
        widget: 需要绑定提示信息的 tkinter 控件。
        text (str): 提示信息文本。
        condition (tuple, optional): 一个元组，形式为 (数值, (最小允许值, 最大允许值))。
                                     - 数值: 用于判断的当前值。
                                     - 最小允许值: 若为 None，则不限制最小值。
                                     - 最大允许值: 若为 None，则不限制最大值。

    操作:
        - 如果 condition 满足范围条件，则绑定提示信息。
        - 如果 condition 不满足范围条件，则解绑提示信息。
    """
    if condition is not None:
        # 解包 condition
        value, (min_value, max_value) = condition

        # 判断条件是否满足
        is_valid = True
        if min_value is not None:
            is_valid = is_valid and (value >= min_value)
        if max_value is not None:
            is_valid = is_valid and (value <= max_value)

        # 根据条件判断是否绑定或解绑提示
        if is_valid:
            if widget not in tooltips:
                tooltips[widget] = Tooltip(widget, text)
        else:
            if widget in tooltips:
                tooltips[widget].widget.unbind("<Enter>")
                tooltips[widget].widget.unbind("<Leave>")
                del tooltips[widget]
    else:
        # 如果没有传入 condition，直接绑定提示信息
        if widget not in tooltips:
            tooltips[widget] = Tooltip(widget, text)


def disable_button_and_add_tip(tooltips, button, text):
    """
    禁用按钮，启用提示
    :return: None
    """
    button.state(['disabled'])
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
