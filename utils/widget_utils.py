import tkinter as tk


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
