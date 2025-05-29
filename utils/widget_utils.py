import inspect
import re
import tkinter as tk
import webbrowser
from functools import partial, wraps
from tkinter import ttk
from typing import Dict, Union

from public_class.custom_classes import Condition, Conditions


class UnlimitedClickHandler:
    def __init__(self, root, widget, click_func=None, **click_map):
        """
        初始化 ClickHandler 类，接收 root 和外部提供的点击处理函数。
        :param click_func: 通用点击处理函数，接受参数 click_time 和 event
        :param click_map: 若指定每次点击对应的函数，可传入字典形式，如 1=func1, 2=func2
        """
        self.down = False
        self.root = root
        self.widget = widget
        print("待绑定:", widget.nametowidget(widget))
        self.is_menu = isinstance(widget.nametowidget(widget), tk.Menu)
        print(self.is_menu)
        self.click_func = self._wrap_click_func(click_func) if click_func else None
        self.click_count = 0
        self.single_click_id = None

        self.func_map = {}
        for k, func in click_map.items():
            try:
                click_num = int(k)
                if click_num >= 1:
                    self.func_map[click_num] = self._wrap_func(func)
            except (ValueError, TypeError):
                # 跳过无法转换为整数的 key
                pass

        # 绑定鼠标点击事件
        widget.bind("<ButtonRelease-1>", self.on_click_up, add=True)
        widget.bind("<Button-1>", self.on_click_down, add=True)

    @staticmethod
    def _wrap_click_func(func):
        """包装通用 click_func，保证接受 click_time 和 event"""
        if not callable(func):
            return lambda click_time, event=None: None

        sig = inspect.signature(func)
        params = list(sig.parameters)

        if len(params) == 1:
            # 只接受 click_time
            def wrapper(click_time, event=None):
                return func(click_time)

            return wrapper
        elif len(params) == 2:
            # 接受 click_time 和 event
            return func
        else:
            # 参数不匹配，返回空函数
            return lambda click_time, event=None: None

    @staticmethod
    def _wrap_func(func):
        """包装函数，保证接受 event 参数，即便原函数不需要"""
        if callable(func):
            sig = inspect.signature(func)
            if len(sig.parameters) == 0:
                # 原函数不接受参数，包装为带 event 参数的版本
                @wraps(func)
                def wrapper(event=None):
                    if event:
                        pass
                    return func()

                return wrapper
            else:
                # 原函数接受 event 参数，原样返回
                return func
        else:
            # 返回一个空的 event 接收函数，避免程序崩溃
            def noop(event=None):
                if event:
                    pass

            return noop

    def on_click_up(self, event=None):
        """处理点击事件（单击、双击、三击等）"""
        print("抬起了")
        self.down = False

    def on_click_down(self, event=None):
        """处理点击事件（单击、双击、三击等）"""
        print("按下了")
        print("控件:", self.widget)
        self.down = True
        self.click_count += 1  # 增加点击次数
        # print(f"点击了控件：{event.widget}")
        print(f"点击次数：{self.click_count}")
        # 取消之前的延时处理（如果有）
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)

        # 设置一个延时，等待是否有更多的点击
        self.single_click_id = self.root.after(200, self.handle_click, event)

    def handle_click(self, event=None):
        click_count = self.click_count
        self.click_count = 0
        if not self.is_menu and self.down:
            print("仍在按下，不处理点击事件")
            return
        if self.click_func:
            self.click_func(click_count, event)
        else:
            matched_count = max(
                (k for k in self.func_map if k <= click_count),
                default=None
            )
            if matched_count:
                partial(self.func_map[matched_count], event=event)()


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        # print(f"{widget}绑定{text}")
        self.widget.bind("<Enter>", self.show, add=True)
        self.widget.bind("<Leave>", self.hide, add=True)

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


class TreeUtils:
    class CopiedTreeData:
        def __init__(self, tree):
            self.items = self.get_all_items_recursive(tree)

        def get_all_items_recursive(self, t, parent=""):
            """
            递归获取所有节点的数据，包括父节点
            :param t: TreeView 实例
            :param parent: 当前父节点
            :return: 包含所有节点数据的列表
            """
            items = []
            for child in t.get_children(parent):
                item_data = {
                    "values": t.item(child)["values"],
                    "text": t.item(child)["text"],
                    "image": t.item(child)["image"],
                    "tags": t.item(child)["tags"],
                    "iid": child,  # 包括 iid
                    "parent": parent  # 记录父节点
                }
                items.append(item_data)
                # 递归获取子节点的数据
                items.extend(self.get_all_items_recursive(t, parent=child))
            return items

        def insert_items(self, tree, parent=""):
            """
            递归插入数据，保持层级关系
            :param tree: TreeView 实例
            :param parent: 当前父节点
            """
            items = self.items

            for item in items:
                # print(f"轮到{items}中的{item}")
                if item["parent"] == parent:
                    tree.insert(
                        parent,
                        "end",
                        iid=item["iid"],
                        text=item["text"],
                        image=item["image"],
                        values=item["values"],
                        tags=item["tags"],
                        open=True
                    )
                    # 插入子节点
                    self.insert_items(tree, parent=item["iid"])

    @staticmethod
    def count_visible_rows_recursive(tree, item_id):
        """
        递归计算tree中item_id及其子节点的行数
        :param tree: 树
        :param item_id: 节点id
        :return: 节点下可见行数（含自身）
        """
        # 如果节点是展开的，计算它和它所有子节点的行数
        total_rows_of_items = 1  # 当前节点占一行
        is_open = tree.item(item_id, "open")
        # print(f"{item_id}的展开状态：{is_open}")
        if is_open == 1 or is_open is True:  # 如果节点展开，遍历它的子节点
            for child in tree.get_children(item_id):
                total_rows_of_items += TreeUtils.count_visible_rows_recursive(tree, child)
        # print(f"{item_id}及其子节点的行数：{total_rows_of_items}")
        return total_rows_of_items

    @staticmethod
    def get_all_leaf_items_recursive(tree, item_id=None):
        """
        递归获取 tree 中所有叶子节点的 iid
        :param tree: 树
        :param item_id: 当前节点的 iid，默认为 None，表示从根节点开始遍历
        :return: 叶子节点 iid 列表
        """
        leaf_items = []

        # 如果没有传入 item_id，默认为根节点
        if item_id is None:
            item_id = ""  # 根节点的 iid 通常是 ""

        # 获取当前节点的所有子节点
        children = tree.get_children(item_id)

        if not children:  # 如果没有子节点，当前节点是叶子节点
            leaf_items.append(item_id)
        else:
            # 否则，递归遍历所有子节点
            for child in children:
                leaf_items.extend(TreeUtils.get_all_leaf_items_recursive(tree, child))  # 递归调用获取子节点的叶子节点

        return leaf_items

    @staticmethod
    def remove_a_tag_of_item(tree, item_id, tag_to_remove):
        current_tags = tree.item(item_id, "tags")
        if isinstance(current_tags, str) and current_tags == "":
            current_tags = ()  # 将空字符串转换为元组
        new_tags = tuple(tag for tag in current_tags if tag != tag_to_remove)
        tree.item(item_id, tags=list(new_tags))
        # print(current_tags, new_tags, tree.item(item_id, "tags"))

    @staticmethod
    def add_a_tag_to_item(tree, item_id, tag_to_add):
        current_tags = tree.item(item_id, "tags")
        if isinstance(current_tags, str) and current_tags == "":
            current_tags = ()  # 将空字符串转换为元组
        current_tags = tuple(tag for tag in current_tags if tag != tag_to_add)  # 先去除，再添加
        new_tags = current_tags + (tag_to_add,)
        tree.item(item_id, tags=list(new_tags))
        # print(current_tags, new_tags, tree.item(item_id, "tags"))

    @staticmethod
    def get_all_items(tree, parent=""):
        items = []
        children = tree.get_children(parent)
        for child in children:
            items.append(child)
            items.extend(TreeUtils.get_all_items(tree, child))
        return items


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


def insert_as_two_per_line(text_widget, line_list):
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


def bind_event_to_frame_when_(widget, event, func, condition: Union[Condition, Conditions, bool]):
    """
    当条件满足时，绑定事件到控件范围内所有位置
    :param widget: 控件
    :param event: 事件
    :param func: 函数
    :param condition: 条件
    :return: None
    """
    # 初始化解绑已有的事件
    widget.nametowidget(widget).unbind(event)
    for child in widget.winfo_children():
        child.unbind(event)

    if condition is True or hasattr(condition, "check") and condition.check():
        widget.bind(event, func, add=True)
        for child in widget.winfo_children():
            child.bind(event, func, add=True)


def enable_widget_when_(widget, condition: Union[Condition, Conditions, bool]):
    """有条件地启用控件"""
    # 设置控件状态
    if condition is True or hasattr(condition, "check") and condition.check():
        widget.config(state="normal")
    else:
        widget.config(state="disabled")


def set_widget_tip_when_(tooltips, widget, tip_condition_dict: Dict[str, Union[Condition, Conditions, bool]]):
    """有条件地设置控件提示"""
    # 初始化解绑已有的提示
    widget.nametowidget(widget).unbind("<Enter>")
    widget.nametowidget(widget).unbind("<Leave>")

    for tip, condition in tip_condition_dict.items():
        # # 根据条件判断是否绑定或解绑提示
        if condition is True or hasattr(condition, "check") and condition.check():
            if widget not in tooltips:
                tooltips[widget] = dict()
            tooltips[widget][tip] = Tooltip(widget, tip)
        else:
            if widget in tooltips and tip in tooltips[widget]:
                del tooltips[widget][tip]
                if len(tooltips[widget]) == 0:
                    del tooltips[widget]


def set_all_children_in_frame_to_state(frame, state):
    """
    设置指定框架及其所有子控件的启用/禁用状态
    :param frame: 要操作的框架（tk.Frame 或 ttk.Frame）
    :param state: 要设置的状态（'normal' 或 'disabled'）
    """
    for widget in frame.winfo_children():
        # 如果是Frame，递归设置子控件
        if isinstance(widget, (tk.Frame, ttk.Frame)):
            set_all_children_in_frame_to_state(widget, state)
        else:
            try:
                widget.config(state=state)
            except Exception as e:
                print(e)
