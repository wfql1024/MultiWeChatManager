import queue
import sys
import tkinter as tk
from abc import ABC, abstractmethod
from functools import partial
from itertools import chain
from tkinter import ttk
from typing import Dict

from functions import subfunc_file, subfunc_sw
from resources import Constants
from utils import widget_utils, string_utils, debug_utils
from utils.logger_utils import mylogger as logger
from utils.widget_utils import TreeUtils
import keyboard


class HotkeyEntry4Keyboard:
    SHIFT_SYMBOL_MAP = {
        "(": "9", "*": "8", "&": "7", "^": "6", "%": "5", "$": "4", "#": "3", "@": "2", "!": "1", ")": "0",
        "_": "-", "+": "=", "~": "`",
        "}": "]", "{": "[", "|": "\\",
        ":": ";", '"': "'",
        "<": ",", ">": ".", "?": "/",
        "left windows": "Win", "right windows": "Win",
        "left ctrl": "Ctrl", "right ctrl": "Ctrl",
        "left alt": "Alt", "right alt": "Alt",
        "left shift": "Shift", "right shift": "Shift",
    }

    def __init__(self, set_hotkey, hotkey_frame):
        self.last_valid_hotkey = ""
        self.current_keys = set()
        self.hotkey_var = tk.StringVar(value="") if set_hotkey is None else tk.StringVar(value=set_hotkey)
        self.hotkey_entry = ttk.Entry(hotkey_frame, textvariable=self.hotkey_var, width=30)
        self.hotkey_entry.pack(side=tk.LEFT)

        # 绑定焦点事件
        self.hotkey_entry.bind("<FocusIn>", self.start_recording)
        self.hotkey_entry.bind("<FocusOut>", self.stop_recording)

    def start_recording(self, event=None):
        """ 开始监听键盘 """
        if event:
            pass
        self.current_keys.clear()

        keyboard.hook(self.on_key_event)

    @staticmethod
    def stop_recording(event=None):
        """ 停止监听键盘 """
        if event:
            pass
        keyboard.unhook_all()

    def on_key_event(self, event):
        """ 处理按键事件（按下/松开） """
        key = self.normalize_key(event.name, event)

        if event.event_type == "down":
            self.current_keys.add(key)
        elif event.event_type == "up":
            self.current_keys.discard(key)

        hotkey_text = "+".join(self.sort_keys(self.current_keys))
        self.hotkey_var.set(hotkey_text)
        if self.is_valid_hotkey(self.current_keys):
            self.last_valid_hotkey = hotkey_text

        if event.event_type == "up":
            self.hotkey_var.set(self.last_valid_hotkey)

    def normalize_key(self, key, event):
        """ 标准化按键（避免 Shift+符号 变成两个快捷键） """
        # print(key)
        if event:
            pass
        if key.lower() in self.SHIFT_SYMBOL_MAP:
            key = self.SHIFT_SYMBOL_MAP[key]  # 统一成非 Shift 状态下的符号
            # print(key)
        return key.capitalize()  # 统一大小写，如 k → K

    @staticmethod
    def sort_keys(keys):
        """ 按 Ctrl → Alt → Shift → Win → 其他 的顺序排序 """
        order = {"Ctrl": 1, "Alt": 2, "Shift": 3, "Win": 4}
        return sorted(keys, key=lambda k: order.get(k, 5))

    @staticmethod
    def is_valid_hotkey(keys):
        """ 判断快捷键是否有效（必须包含 1 个非修饰键 + 至少 1 个修饰键，F1~F12 可单独存在） """
        modifier_keys = {"Shift", "Ctrl", "Alt", "Win"}
        function_keys = {f"F{i}" for i in range(1, 13)}  # F1~F12 允许单独出现

        non_modifier_keys = [key for key in keys if key not in modifier_keys]

        # 规则：
        # 1. 至少包含 1 个非修饰键 + 1 个修饰键
        # 2. 如果唯一的非修饰键是 F1~F12，则可以单独出现
        valid = (
                        len(non_modifier_keys) == 1 and any(key in modifier_keys for key in keys)
                ) or (len(non_modifier_keys) == 1 and non_modifier_keys[0] in function_keys)

        return valid


class HotkeyEntry4Tkinter:
    def __init__(self, set_hotkey, hotkey_frame):
        self.last_valid_hotkey = None
        self.current_keys = set()
        self.hotkey_var = tk.StringVar(value="") if set_hotkey is None else tk.StringVar(value=set_hotkey)
        self.hotkey_entry = ttk.Entry(hotkey_frame, textvariable=self.hotkey_var, width=30)
        self.hotkey_entry.pack(side=tk.LEFT)

        # 绑定事件
        self.hotkey_entry.bind("<FocusIn>", self.start_recording)
        self.hotkey_entry.bind("<KeyPress>", self.on_key_press)
        self.hotkey_entry.bind("<KeyRelease>", self.on_key_release)

    def start_recording(self, event):
        """ 清空当前录制状态 """
        if event:
            pass
        self.current_keys.clear()

    @staticmethod
    def normalize_key(key, keycode):
        """ 统一按键名称，包括修饰键、数字键、字母键大小写 """
        key_map = {
            "Shift_L": "Shift", "Shift_R": "Shift",
            "Control_L": "Ctrl", "Control_R": "Ctrl",
            "Alt_L": "Alt", "Alt_R": "Alt",
            "Win_L": "Win", "Win_R": "Win",
            "minus": "-", "equal": "=",
            "comma": ",", "period": ".",
            "slash": "/", "backslash": "\\",
            "bracketleft": "[", "bracketright": "]",
            "semicolon": ";", "quoteright": "'",
            "quoteleft": "`", "space": "Space"
        }

        # 修饰键归一化
        if key in key_map:
            return key_map[key]

        # 数字键（不受 Shift 影响）
        if keycode in range(48, 58):  # 0-9
            return chr(keycode)

        # 字母键始终大写
        if len(key) == 1 and key.isalpha():
            return key.upper()

        return key  # 其他按键保持原样

    @staticmethod
    def sort_keys(keys):
        """ 按 Ctrl → Alt → Shift → Win → 其他 的顺序排序 """
        order = {"Ctrl": 1, "Alt": 2, "Shift": 3, "Win": 4}
        return sorted(keys, key=lambda k: order.get(k, 5))  # 未定义的按键放最后

    @staticmethod
    def is_valid_hotkey(keys):
        """ 判断快捷键是否有效（是否包含非修饰键） """
        modifier_keys = {"Shift", "Ctrl", "Alt", "Win"}
        non_modifier_keys = [key for key in keys if key not in modifier_keys]  # 找出所有非修饰键
        # 判断方式：需要包含非修饰键，且至少有一个修饰键
        valid = len(non_modifier_keys) == 1 and any(key in modifier_keys for key in keys)
        print(f"{keys}是valid={valid}")
        return valid

    def on_key_press(self, event):
        key = self.normalize_key(event.keysym, event.keycode)
        print("按着", key, chr(event.keycode))
        self.current_keys.add(key)

        hotkey_text = "+".join(self.sort_keys(self.current_keys))
        print(hotkey_text)
        self.hotkey_var.set(hotkey_text)

        if self.is_valid_hotkey(self.current_keys):
            self.last_valid_hotkey = hotkey_text

        return "break"

    def on_key_release(self, event):
        key = self.normalize_key(event.keysym, event.keycode)
        print("松开", key)
        if "??" in self.current_keys:
            self.current_keys.remove("??")
        if key in self.current_keys:
            self.current_keys.remove(key)
        self.hotkey_var.set(self.last_valid_hotkey)

        return "break"


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


class ScrollableCanvas:
    def __init__(self, master_frame):
        self.master_frame = master_frame

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        scrollbar_frame = tk.Frame(self.master_frame)
        scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.master_frame, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        # print("创建滚动条...")
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

    def refresh_canvas(self):
        # 加载完成后更新一下界面并且触发事件
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)
        pass


class ActionableTreeView(ABC):
    def __init__(self, parent_class, login_status, title_text, major_btn_dict, *rest_btn_dicts):
        """
        创建一个TreeView列表，可全选、多选，可以批量添加能对选中的条目进行操作的按钮，可以对单个条目的id列添加功能交互
        :param parent_class: 实例该列表的类
        :param login_status: 表标识
        :param title_text: 列表标题
        :param major_btn_dict: 主按钮信息
        :param rest_btn_dicts: 其他按钮信息
        """
        self.tree_frame = None
        self.button_frame = None
        self.label = None
        self.title_frame = None
        self.hovered_item = None
        self.checkbox_var = None
        self.title = None
        self.checkbox = None
        self.tooltips = {}
        self.selected_items = []
        self.func_of_id_col = None

        self.sort: Dict[str, bool] = {

        }
        self.default_sort = {
            "col": "#0",
            "is_asc": True
        }
        self.columns: tuple = ("子类请传入列的元组self.columns", "该列全屏不隐藏", "set_table_style中调列宽")
        self.selected_values: Dict[str, Dict] = {
            "column": {},
            "relate_chain": {}
        }

        # 将传入的参数赋值给成员变量
        self.parent_class = parent_class
        self.table_tag = login_status
        self.title_text = title_text
        self.major_btn_dict = major_btn_dict
        self.rest_btn_dicts = rest_btn_dicts

        # 其他的成员变量
        self.root = self.parent_class.root
        self.root_class = self.parent_class.root_class
        self.main_frame = self.parent_class.main_frame
        self.sw = self.root_class.sw

        self.initialize_members_in_init()

        self.create_title()
        self.tree = self.create_table(self.columns)
        self.display_table()
        self.adjust_table()

    def create_title(self):
        self.tree_frame = ttk.Frame(self.main_frame)
        self.tree_frame.pack(side=tk.TOP, fill=tk.X)

        # 框架=标题+列表
        self.title_frame = ttk.Frame(self.tree_frame)
        self.title_frame.pack(side=tk.TOP, fill=tk.X,
                              padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

        # 标题=复选框+标签+按钮区域
        self.title = ttk.Frame(self.title_frame)
        self.title.pack(side=tk.TOP, fill=tk.X)

        # 复选框
        self.checkbox_var = tk.IntVar(value=0)
        self.checkbox = tk.Checkbutton(
            self.title,
            variable=self.checkbox_var,
            tristatevalue=-1
        )
        self.checkbox.pack(side=tk.LEFT)

        # 标签
        self.label = ttk.Label(self.title, text=self.title_text,
                               style='FirstTitle.TLabel')
        self.label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

        # 按钮区域
        self.button_frame = ttk.Frame(self.title)
        self.button_frame.pack(side=tk.RIGHT)

        # 主按钮
        if self.major_btn_dict is not None:
            major_btn = ttk.Button(
                self.button_frame, text=self.major_btn_dict["text"], style='Custom.TButton',
                command=lambda: self.major_btn_dict["func"](self.selected_items))
            self.major_btn_dict["btn"] = major_btn
            major_btn.pack(side=tk.RIGHT)

        # 加载其他按钮
        # print(self.rest_btn_dicts)
        if self.rest_btn_dicts is not None and len(self.rest_btn_dicts) != 0:
            for btn_dict in self.rest_btn_dicts:
                btn = ttk.Button(
                    self.button_frame, text=btn_dict["text"], style='Custom.TButton',
                    command=lambda b=btn_dict: b["func"](self.selected_items))
                btn_dict["btn"] = btn
                btn.pack(side=tk.RIGHT)

    @abstractmethod
    def initialize_members_in_init(self):
        """子类中重写方法若需要设置或新增成员变量，重写这个方法并在其中定义和赋值成员"""
        pass

    def create_table(self, columns: tuple = ()):
        """定义表格，根据表格类型选择手动或自动登录表格"""
        tree = ttk.Treeview(self.tree_frame, columns=columns, show='tree', height=1, style="RowTreeview")

        # 设置列标题和排序功能
        for col in columns:
            tree.heading(
                col, text=col,
                command=lambda c=col: self.apply_or_switch_col_order(c)
            )
            tree.column(col, anchor='center')  # 设置列宽
            self.sort[col] = True
        tree.pack(fill=tk.X, expand=True, padx=(10, 0))
        return tree

    def display_table(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)
        values = tuple("请重写展示数据方法" for _ in tree["columns"])
        tree.insert("", "end", iid="item1", text="示例项", values=values)
        pass

    def set_table_style(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)

        # 默认情况下
        selected_bg = "#B2E0F7"
        hover_bg = "#E5F5FD"
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")

        # 以下为自定义样式示例
        # # 特定列的宽度和样式设置
        # tree.column("#0", minwidth=100, width=100, stretch=tk.YES)
        #
        # # 在非全屏时，隐藏特定列
        # columns_to_hide = ["该列全屏不隐藏"]
        # col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        # tree.bind("<Configure>", lambda e: self.adjust_columns_on_maximize_(
        #     e, self.root, col_width_to_show, columns_to_hide), add='+')
        pass

    def get_selected_values(self):
        # 获取选中行的“账号”列数据
        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_items
        # print(selected_items)
        # print([tree.item(i) for i in selected_items])

        # 开辟一个新的字典，存储每一列的选中行的值
        for index, column in enumerate(tree["columns"]):
            selected_values_of_column = []
            for i in selected_items:
                try:
                    value = tree.item(i, "values")[index]
                    selected_values_of_column.append(value)
                except IndexError:
                    # 超出范围，跳过当前项
                    continue
            self.selected_values["column"][column] = selected_values_of_column

        # 添加 relate_chain 逻辑
        self.selected_values["relate_chain"] = {}
        for item_id in selected_items:
            relate_chain = []
            current_id = item_id
            while current_id:  # 一直向上查找父节点，直到根节点
                relate_chain.append(current_id)
                current_id = tree.parent(current_id)  # 获取父节点的 ID
            self.selected_values["relate_chain"][item_id] = relate_chain

        print(self.selected_values)
        print(tree.selection())

    def toggle_top_checkbox(self, _event):
        """
        切换顶部复选框状态，更新子列表
        :param _event: 触发事件的控件
        :return: 阻断继续切换
        """
        # print(event.widget)
        # print(self.login_checkbox)
        checkbox_var = self.checkbox_var
        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_items

        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        all_leaf_rows = TreeUtils.get_all_leaf_items_recursive(tree)
        for item_id in all_leaf_rows:
            if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                if value:
                    # 执行全选
                    # print(tree.item(item_id, "tags"))
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                else:
                    # 取消所有选择
                    selected_items.clear()
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")

        # 获取选中行的数据包以及根据选中情况更新顶部状态
        self.get_selected_values()
        self.update_top_title()
        return "break"

    def update_top_title(self):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox)
        tree = self.tree.nametowidget(self.tree)

        all_leaf_rows = TreeUtils.get_all_leaf_items_recursive(tree)
        selected_rows = self.selected_items
        title = self.title
        checkbox_var = self.checkbox_var
        checkbox = self.checkbox
        tooltips = self.tooltips
        major_btn_dict = self.major_btn_dict
        rest_btn_dicts = self.rest_btn_dicts

        # 根据列表是否有可选设置复选框相关事件的绑定
        if len(all_leaf_rows) == 0:
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
        else:
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")

            # 根据子列表的状态来更新顶部复选框
            if len(selected_rows) == len(all_leaf_rows):
                checkbox_var.set(1)
            elif 0 < len(selected_rows) < len(all_leaf_rows):
                checkbox_var.set(-1)
            else:
                checkbox_var.set(0)

        # 控件的状态设置和提示设置
        widget_utils.enable_widget_with_condition(checkbox, (len(all_leaf_rows), [(1, None)]))

        # 使用 chain 合并 major_btn_dict 和 btn_dicts，并进行遍历
        for btn_dict in chain([major_btn_dict] if major_btn_dict is not None else [], rest_btn_dicts or []):
            if btn_dict is not None:  # 确保 btn_dict 不是 None
                widget_utils.enable_widget_with_condition(
                    btn_dict["btn"], (len(selected_rows), btn_dict["enable_scopes"]))
                widget_utils.set_widget_tip_with_condition(
                    tooltips, btn_dict["btn"], len(selected_rows),
                    btn_dict["tip_scopes_dict"])

    def on_selection_in_tree(self, event=None):
        tree = event.widget
        selected_items = self.selected_items
        item_id = tree.identify_row(event.y)
        self.func_of_id_col = lambda: self.root_class.open_acc_detail(item_id)

        # 列标题不响应
        if len(item_id) == 0:
            return
        # 列表未加载，跳过
        if selected_items is None:
            return

        print("进入了单击判定")

        # 只对叶子节点响应
        if tree.get_children(item_id):
            # print(tree.item(item_id, "open"))
            self.adjust_treeview_height(event)
            self.parent_class.scrollable_canvas.refresh_canvas()
            return

        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            self.func_of_id_col()
            pass
        else:
            if item_id:
                # 不可选的行不触发
                if "disabled" in tree.item(item_id, "tags"):
                    return
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")
                else:
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.get_selected_values()  # 实时更新选中行显示
                self.update_top_title()

    def on_double_selection_in_tree(self, event=None):
        double_click_func = lambda: self.major_btn_dict["func"](self.selected_items)

        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_items
        item_id = tree.identify_row(event.y)
        # print(f"item_id: {item_id}")

        # 对列标题不触发
        if len(item_id) == 0:
            return
        # 不可选的不触发
        if "disabled" in tree.item(item_id, "tags"):
            return

        # 如果节点有子节点，则不触发双击；只对叶子节点触发
        if tree.get_children(item_id):
            # print(tree.item(item_id, "open"))
            self.adjust_treeview_height(event)
            self.parent_class.scrollable_canvas.refresh_canvas()
            return

        # 图片列双击切换窗口
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            subfunc_sw.switch_to_sw_account_wnd(item_id, self.root)
        else:
            if item_id:
                # 取消所有选择
                selected_items.clear()
                for i in tree.get_children():
                    widget_utils.remove_a_tag_of_item(tree, i, "selected")
                # 只选择当前行
                selected_items.append(item_id)
                widget_utils.add_a_tag_to_item(tree, item_id, "selected")

                self.get_selected_values()  # 实时更新选中行显示
                self.update_top_title()
                double_click_func()

    def on_leave(self, _event):
        if self.hovered_item is not None:
            widget_utils.remove_a_tag_of_item(self.hovered_item[0], self.hovered_item[1], "hover")
            self.hovered_item = None

    def on_mouse_motion(self, event):
        tree = event.widget

        # 获取当前鼠标所在的行 ID
        item = tree.identify_row(event.y)

        # 检查是否是新的悬停行
        if self.hovered_item is not None:
            if self.hovered_item[0] != tree or self.hovered_item[1] != item:
                widget_utils.remove_a_tag_of_item(tree, self.hovered_item[1], "hover")
                widget_utils.add_a_tag_to_item(tree, item, "hover")
                # 更新当前悬停行
                self.hovered_item = (tree, item)
        else:
            widget_utils.add_a_tag_to_item(tree, item, "hover")
            # 更新当前悬停行
            self.hovered_item = (tree, item)

    def adjust_columns_on_maximize_(self, event, wnd, col_width_to_show, columns_to_hide=None):
        # print("触发列宽调整")
        tree = self.tree.nametowidget(event.widget)

        if wnd.state() != "zoomed":
            # 非最大化时隐藏列和标题
            tree["show"] = "tree"  # 隐藏标题
            for col in columns_to_hide:
                if col in tree["columns"]:
                    tree.column(col, width=0, stretch=False)
        else:
            # 最大化时显示列和标题
            width = col_width_to_show
            tree["show"] = "tree headings"  # 显示标题
            for col in columns_to_hide:
                if col in tree["columns"]:
                    tree.column(col, width=width)  # 设置合适的宽度

    def adjust_treeview_height(self, event):
        # print("触发表高调整")
        # print(event)
        if event:
            # print(event.y)
            pass

        tree = self.tree.nametowidget(self.tree)

        total_rows = 0
        for root_item in tree.get_children():
            total_rows += TreeUtils.count_visible_rows_recursive(tree, root_item)
        # print(total_rows)
        tree.configure(height=total_rows)

        # return "break"

    def apply_or_switch_col_order(self, col=None):
        """
        切换列排序或应用列排序，支持多级 TreeView，若不传入 col，则应用列排序
        :param col: 列
        :return: 无
        """
        table_tag = self.table_tag
        tree = self.tree.nametowidget(self.tree)

        # 调用递归函数获取所有数据
        copied_data = TreeUtils.CopiedTreeData(tree)
        copied_items = copied_data.items

        # 确定排序的列和顺序
        if col is not None:
            # 切换col的排序，同时把其他列的排序设置为降序，这样下次点击其他列默认升序
            is_asc = self.sort[col] is True
            for c in tree["columns"]:
                if c != col:
                    self.sort[c] = False
            is_asc_after = not is_asc
            print(f"切换列排序：{col},{is_asc_after}")
        else:
            # 获取要应用的列和顺序，若没有则默认用id列排正序
            col = self.default_sort["col"] if self.default_sort["col"] in tree["columns"] else "#0"
            is_asc = (self.default_sort["is_asc"] == "True") if self.default_sort["is_asc"] is not None else True
            is_asc_after = is_asc
            print(f"应用列排序：{col},{is_asc_after}")

        # 排序函数
        if col == "#0":
            # 直接对iid排序
            sort_key_by_float = lambda x: string_utils.try_convert_to_float(x["iid"])
            sort_key_by_str = lambda x: str(x["iid"])
        else:
            # 按列排序
            sort_key_by_float = lambda x: string_utils.try_convert_to_float(
                x["values"][list(tree["columns"]).index(col)])
            sort_key_by_str = lambda x: str(x["values"][list(tree["columns"]).index(col)])

        # 排序
        try:
            copied_items.sort(key=sort_key_by_float, reverse=not is_asc_after)
        except Exception as e:
            logger.warning(e)
            copied_items.sort(key=sort_key_by_str, reverse=not is_asc_after)

        # 清空表格并重新插入排序后的数据，保留父子层级
        for i in tree.get_children():
            tree.delete(i)
        copied_data.insert_items(tree)

        # 根据排序后的行数调整 Treeview 的高度
        tree.configure(height=len(copied_data.items))

        # 保存排序状态
        self.sort[col] = is_asc_after
        subfunc_file.save_sw_setting(self.sw, f'{table_tag}_sort', f"{col},{is_asc_after}")

    def adjust_table(self):
        """
        绑定事件以实现自适应调整表格
        :return: 结束
        """
        tree = self.tree.nametowidget(self.tree)

        if len(tree.get_children()) == 0:
            self.tree_frame.destroy()

        if not self.tree_frame.winfo_exists():
            return

        self.set_table_style()
        self.update_top_title()
        widget_utils.UnlimitedClickHandler(
            self.root,
            tree,
            partial(self.on_selection_in_tree),
            partial(self.on_double_selection_in_tree)
        )
        tree.bind("<Leave>", partial(self.on_leave))
        tree.bind("<Motion>", partial(self.on_mouse_motion))
        self.apply_or_switch_col_order()
        self.adjust_treeview_height(None)
