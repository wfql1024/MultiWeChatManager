import queue
import sys
import tkinter as tk
from tkinter import ttk

import keyboard

from public import Config
from public.custom_classes import QueueWithUpdate
from public.global_members import GlobalMembers
from utils import hwnd_utils
from utils.logger_utils import mylogger as logger, RedirectText


class ProgressBarW:
    """进度条包装类"""

    def __init__(self, parent, height=2):
        self.progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self.height = height
        self._job = None

    @staticmethod
    def with_progress_bar_wrapper_factory(progress_bar):
        """将进度条传入, 返回一个装饰器, 这个装饰器将对装饰的函数过程收尾添加进度条的展示和结束."""
        root = GlobalMembers.root_class.root

        def decorator(func):
            def wrapper(*args, **kwargs):
                root.after(0, progress_bar.loading)
                try:
                    return func(*args, **kwargs)
                finally:
                    root.after(0, progress_bar.finished)

            return wrapper

        return decorator

    @staticmethod
    def with_progress_bar(func):
        """这个装饰器将对装饰的函数过程收尾添加进度条的展示和结束, 这个函数需要有self参数, 并且self需要有progress_bar属性."""

        def wrapper(self, *args, **kwargs):
            self.root.after(0, self.progress_bar.loading)
            try:
                return func(self, *args, **kwargs)
            finally:
                self.root.after(0, self.progress_bar.finished)

        return wrapper

    def _auto_step(self, interval, step):
        """内部循环自增进度，但不超过95"""
        value = self.progress["value"]
        if value < 95:
            self.progress["value"] = min(95, value + step)
            self._job = self.progress.after(interval, self._auto_step, interval, step)

    def loading(self, interval=100, step=30):
        """自动加载进度条 (最多到95)"""
        print("TopProgressBar loading")
        self.progress.pack(fill="x", ipady=0)
        self.progress["value"] = 0
        self._auto_step(interval, step)

    def finished(self):
        """进度条直接充满并停止"""
        if self._job:
            self.progress.after_cancel(self._job)
            self._job = None
        self.progress["value"] = 100
        self.progress.pack_forget()


class CustomDialogW:
    @classmethod
    def ask_username_password(cls):
        result = []  # 使用列表封装以在内部函数中修改

        def on_ok():
            result[0] = (entry_username.get(), entry_password.get())
            window.destroy()

        def on_close():
            result[0] = None
            window.destroy()

        window = tk.Tk()
        window.title("登录")
        window.protocol("WM_DELETE_WINDOW", on_close)

        # 居中窗口
        window.update_idletasks()
        w = window.winfo_width()
        h = window.winfo_height()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        window.geometry(f"{w}x{h}+{x}+{y}")

        # 用户名标签和输入框
        tk.Label(window, text="微软注册邮箱:").pack(pady=(10, 0))
        entry_username = tk.Entry(window)
        entry_username.pack()

        # 密码标签和输入框
        tk.Label(window, text="密码:").pack(pady=(5, 0))
        entry_password = tk.Entry(window, show="*")
        entry_password.pack()

        # 确认按钮
        tk.Button(window, text="确定", command=on_ok).pack(pady=(8, 0))

        window.mainloop()
        return result[0]


class HotkeyEntry4KeyboardW:
    """
    用于监听键盘输入的热键输入框，适配Keyboard模块
    """
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

    def __init__(self, hotkey_entry, hotkey_var):
        self.last_valid_hotkey = ""
        self.current_keys = set()
        self.hotkey_entry = hotkey_entry
        self.hotkey_var = hotkey_var

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


class HotkeyEntry4TkinterW:
    """
    用于监听键盘输入的热键输入框，适配Tkinter
    """

    def __init__(self, set_hotkey, hotkey_frame):
        self.last_valid_hotkey = None
        self.current_keys = set()
        self.hotkey_var = tk.StringVar(value="") if set_hotkey is None else tk.StringVar(value=set_hotkey)
        self.hotkey_entry = ttk.Entry(hotkey_frame, textvariable=self.hotkey_var, width=30)
        self.hotkey_entry.pack(side="left")

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


class StatusBarW:
    """对print即时更新的状态栏"""

    def __init__(self, root, root_frame, debug):
        self.status_bar = None
        self.statusbar_output_var = None

        self.root = root
        self.root_frame = root_frame
        self.debug = debug

        # 创建状态栏
        self.create_status_bar()
        self.message_queue = QueueWithUpdate(self.update_status)  # 创建消息队列
        sys.stdout = RedirectText(self.statusbar_output_var, self.message_queue, self.debug)  # 重定向 stdout

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏...")
        self.statusbar_output_var = tk.StringVar()
        self.status_bar = tk.Label(self.root_frame, textvariable=self.statusbar_output_var, bd=Config.STATUS_BAR_BD,
                                   relief="sunken", anchor="w", height=Config.STATUS_BAR_HEIGHT)
        self.status_bar.pack(side="bottom", fill="x")

    def update_status(self):
        """即时更新状态栏"""
        try:
            # 从队列中获取消息并更新状态栏
            message = self.message_queue.get_nowait()
            if message is not None and message.strip():  # 如果消息不为空，更新状态栏
                self.root.after(0, self.statusbar_output_var.set, message)
        except queue.Empty:
            pass


class ScrollableCanvasW:
    """
    可滚动的Canvas，用于动态调整Canvas中窗口的宽度，并根据父子间高度关系进行滚轮事件绑定与解绑
    """

    def __init__(self, master_frame):
        self._master_frame = master_frame

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        scrollbar_frame = tk.Frame(self._master_frame)
        scrollbar_frame.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self._master_frame, highlightthickness=0)
        self.canvas.pack(fill="both", side="left", expand=True)

        # 创建滚动条
        # print("创建滚动条...")
        self._scrollbar = ttk.Scrollbar(scrollbar_frame, orient="vertical", command=self.canvas.yview)
        self._scrollbar.pack(side="left", fill="y")
        # 创建一个Frame在Canvas中
        self.main_frame = ttk.Frame(self.canvas)
        # 将main_frame放置到Canvas的窗口中，并禁用Canvas的宽高跟随调整
        self._canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        # 将滚动条连接到Canvas
        self.canvas.configure(yscrollcommand=self._scrollbar.set)
        # 配置Canvas的滚动区域
        self.canvas.bind('<Configure>', self._on_canvas_configure)

    def _bind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", self._on_mousewheel, add='+')
        widget.bind("<Button-4>", self._on_mousewheel, add='+')
        widget.bind("<Button-5>", self._on_mousewheel, add='+')

        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _unbind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.unbind("<MouseWheel>")
        widget.unbind("<Button-4>")
        widget.unbind("<Button-5>")

        for child in widget.winfo_children():
            self._unbind_mouse_wheel(child)

    def _on_mousewheel(self, event):
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

    def _on_canvas_configure(self, event):
        """动态调整canvas中窗口的宽度，并根据父子间高度关系进行滚轮事件绑定与解绑"""
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            width = event.width
            self.canvas.itemconfig(tagOrId=self._canvas_window, width=width)
            if self.main_frame.winfo_height() > self.canvas.winfo_height():
                self._bind_mouse_wheel(self.canvas)
                self._scrollbar.pack(side="left", fill="y")
            else:
                self._unbind_mouse_wheel(self.canvas)
                self._scrollbar.pack_forget()
        except Exception as e:
            logger.error(e)

    def refresh_canvas(self):
        # 加载完成后更新一下界面并且触发事件
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self._on_canvas_configure(event)
        pass


class SubToolWndUI:
    def __init__(self, wnd, title):
        """
        这是一个层级敏感的窗口类，当关闭时，会自动恢复父窗口的焦点. 所有内容请放在 wnd_frame 中
        :param wnd:
        :param title:
        """
        self.close_when_open = None  # 撤回一个窗口(哈哈
        self.position = None
        self.wnd_height = None
        self.wnd_width = None

        self.wnd = wnd
        self.title = title

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root

        self.initialize_members_in_init()

        wnd.withdraw()  # 隐藏窗口

        # 设置窗口
        wnd.title(self.title)
        wnd.attributes('-toolwindow', True)
        self.wnd_frame = tk.Frame(wnd)
        self.wnd_frame.pack(fill="both", expand=True)
        self.set_wnd()
        self.load_ui()
        self.update_content()
        wnd.update_idletasks()
        hwnd_utils.set_size_and_bring_tk_wnd_to_(wnd, self.wnd_width, self.wnd_height, self.position)

        if self.close_when_open is not True:
            wnd.deiconify()  # 显示窗口
            wnd.grab_set()
        wnd.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.close_when_open is True:
            self._on_close()

    def initialize_members_in_init(self):
        """
        子类中重写方法若需要设置或新增成员变量，重写这个方法并在其中定义和赋值成员
        一些固定的变量名：
            self.position: 窗口位置
            self.wnd_height: 窗口高度
            self.wnd_width: 窗口宽度
        """
        pass

    def set_wnd(self):
        """
        除去本类基本的设置外，其余窗口设置可以在此方法中书写
        已经设置好的窗口属性：工具窗口属性、默认可以调节大小
        """
        ...

    def load_ui(self):
        """加载基本的 UI 和默认数据"""
        ...

    def update_content(self):
        """更新窗口内容"""
        ...

    def finally_do(self):
        ...

    def _on_close(self):
        """窗口关闭时执行的操作"""
        # 关闭前
        self.finally_do()

        master_wnd = self.wnd.master
        self.wnd.destroy()  # 关闭窗口
        if master_wnd != self.root:
            master_wnd.grab_set()  # 恢复父窗口的焦点
