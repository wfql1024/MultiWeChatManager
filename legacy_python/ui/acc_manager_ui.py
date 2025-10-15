import tkinter as tk
from abc import ABC
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from legacy_python.components.composited_controls import TreeviewAHT
from legacy_python.components.widget_wrappers import SubToolWndUI, ScrollableCanvasW
from legacy_python.functions import subfunc_file
from legacy_python.functions.acc_func import AccInfoFunc
from legacy_python.functions.app_func import AppFunc
from legacy_python.public import Config
from legacy_python.public.custom_classes import Condition
from legacy_python.public.enums import AccKeys
from legacy_python.public.global_members import GlobalMembers
from legacy_python.ui.wnd_ui import WndCreator
from legacy_python.utils.encoding_utils import StringUtils
from legacy_python.utils.logger_utils import mylogger as logger
from legacy_python.utils.logger_utils import myprinter as printer


class AccManagerWndUI(SubToolWndUI, ABC):
    """账号管理窗口"""

    def __init__(self, wnd, title):
        self.acc_manager_ui = None
        self.sw = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Config.ACC_MNG_WND_SIZE
        self.acc_manager_ui = AccManagerUI(self.wnd, self.wnd)

    def load_ui(self):
        self.acc_manager_ui.refresh_frame()
        pass

    def update_content(self):
        self.acc_manager_ui.display_ui()


class AccManagerUI:
    """账号管理UI"""

    def __init__(self, wnd, frame):
        print("构建账号管理ui...")

        self.quick_refresh_mode = None
        self.root_menu = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.acc_data = None
        self.tree_class = {}
        self.frame_dict = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.wnd = wnd
        self.tab_frame = frame
        self.btn_dict = {
            "cancel_hiding_btn": {
                "text": "取消隐藏",
                "btn": None,
                "func": self._create_set_acc_method(AccKeys.HIDDEN, False),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要取消隐藏的账号": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "cancel_auto_start_btn": {
                "text": "取消自启",
                "btn": None,
                "func": self._create_set_acc_method(AccKeys.AUTO_START, False),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要取消自启的账号": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
            },
            "add_hiding_btn": {
                "text": "隐藏",
                "btn": None,
                "func": self._create_set_acc_method(AccKeys.HIDDEN, True),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要隐藏的账号": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                },
            },
            "add_auto_start_btn": {
                "text": "自启",
                "btn": None,
                "func": self._create_set_acc_method(AccKeys.AUTO_START, True),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要自启的账号": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
            },
            "add_hotkey_btn": {
                "text": "添加热键",
                "btn": None,
                "func": self.to_add_hotkey_of_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, 1)]),
                "tip_scopes_dict": {
                    "请选择一个要添加热键的账号": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                    "一个一个来啦~": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(2, None)])
                },
            }
        }

    def init_acc_manager_ui(self):
        """初始化账号管理UI"""
        if self.tab_frame is None or len(self.tab_frame.winfo_children()) == 0:
            self.refresh()
        else:
            self.refresh(True)

    def refresh(self, only_menu=False):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")
        # 刷新菜单
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if config_data is None:
            messagebox.showerror("错误", "配置文件获取失败，将关闭软件，请检查网络后重启")
            self.root.destroy()
        try:
            self.root.after(0, self.root_class.menu_ui.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            messagebox.showerror("错误", "配置文件损坏，将关闭软件，请检查网络后重启")
            self.root.destroy()

        if only_menu is True:
            return
        # 刷新界面
        try:
            self.root.after(0, self.refresh_frame)
        except Exception as e:
            logger.error(e)
            self.root.after(3000, self.refresh_frame)

    def display_ui(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = ScrollableCanvasW(self.tab_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        # 添加占位控件
        self.frame_dict["auto_start"] = ttk.Frame(self.main_frame)
        self.frame_dict["auto_start"].pack(side=tk.TOP, fill=tk.X)
        self.frame_dict["hidden"] = ttk.Frame(self.main_frame)
        self.frame_dict["hidden"].pack(side=tk.TOP, fill=tk.X)
        self.frame_dict["all"] = ttk.Frame(self.main_frame)
        self.frame_dict["all"].pack(side=tk.TOP, fill=tk.X)

        self.acc_data = subfunc_file.get_sw_acc_data()
        # 加载已自启列表
        self.tree_class["auto_start"] = AccManagerTAHT(
            self, self.frame_dict["auto_start"],
            "auto_start", "已自启：", self.btn_dict["cancel_auto_start_btn"].copy())
        # 加载已隐藏列表
        self.tree_class["hidden"] = AccManagerTAHT(
            self, self.frame_dict["hidden"],
            "hidden", "已隐藏：", self.btn_dict["cancel_hiding_btn"].copy())
        # 加载所有
        self.tree_class["all"] = AccManagerTAHT(
            self, self.frame_dict["all"],
            "all", "所有账号：", None,
            self.btn_dict["add_auto_start_btn"].copy(),
            self.btn_dict["add_hiding_btn"].copy(),
            self.btn_dict["add_hotkey_btn"].copy()
        )

        print("账号管理页面列表都加载完...")

        # 加载完成后更新一下界面并且触发事件
        if self.scrollable_canvas is not None and self.scrollable_canvas.canvas.winfo_exists():
            self.scrollable_canvas.refresh_canvas()

    def _create_set_acc_method(self, key, value):
        def set_acc_method(items):
            for item in items:
                sw, acc = item.split("/")
                subfunc_file.update_sw_acc_data(sw, acc, **{key: value})
            self.refresh_frame()

        return set_acc_method

    def to_add_hotkey_of_(self, items):
        WndCreator.open_acc_detail(items[0], self, "hotkey")

    def refresh_frame(self, sw=None):
        print("进入账号管理刷新")
        if sw:
            pass

        def slowly_refresh():
            if isinstance(self.tab_frame, ttk.Frame) and self.tab_frame.winfo_exists():
                printer.vital("刷新页面")
                for widget in self.tab_frame.winfo_children():
                    widget.destroy()
            self.display_ui()

        if self.quick_refresh_mode is True:
            try:
                # 不要忘记更新数据
                self.acc_data = subfunc_file.get_sw_acc_data()
                tree_class = self.tree_class
                if all(tree_class[t].can_quick_refresh for t in tree_class):
                    for t in tree_class:
                        tree_class[t].quick_refresh_items()
            except Exception as e:
                logger.warning(e)
                self.quick_refresh_mode = False
                slowly_refresh()
        else:
            slowly_refresh()
        printer.print_vn("加载完成!")


class AccManagerTAHT(TreeviewAHT):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.can_quick_refresh = None
        self.wnd = None
        self.photo_images = []
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.wnd = self.parent_class.wnd
        # print(f"self.wnd={self.wnd}")
        self.columns = (" ", "快捷键", "隐藏", "自启动", "账号标识", "昵称")
        self.main_frame = self.parent_class.frame_dict[self.table_tag]
        sort_str = AppFunc.get_global_setting_value_by_local_record(f"{self.table_tag}_sort")
        if isinstance(sort_str, str):
            if len(sort_str.split(",")) == 2:
                self.default_sort["col"], self.default_sort["is_asc"] = sort_str.split(",")

    def set_tree_style(self):
        super().set_tree_style()

        tree = self.tree
        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Config.COLUMN_MIN_WIDTH["SEC_ID"],
                    width=Config.COLUMN_WIDTH["SEC_ID"], stretch=tk.NO)
        tree.column(" ", minwidth=Config.COLUMN_MIN_WIDTH["展示"],
                    width=Config.COLUMN_WIDTH["展示"], anchor='w')
        tree.column("快捷键", minwidth=Config.COLUMN_MIN_WIDTH["快捷键"],
                    width=Config.COLUMN_WIDTH["快捷键"], anchor='center', stretch=tk.NO)
        tree.column("自启动", minwidth=Config.COLUMN_MIN_WIDTH["自启动"],
                    width=Config.COLUMN_WIDTH["自启动"], anchor='center', stretch=tk.NO)
        tree.column("隐藏", minwidth=Config.COLUMN_MIN_WIDTH["隐藏"],
                    width=Config.COLUMN_WIDTH["隐藏"], anchor='center', stretch=tk.NO)
        tree.column("账号标识", anchor='center')
        tree.column("昵称", anchor='center')

    def display_tree(self):
        tree = self.tree.nametowidget(self.tree)
        sw_acc_data = self.parent_class.acc_data
        table_tag = self.table_tag

        # 假设你已经有了一个用于存储 sw 节点的字典
        sw_nodes = {}

        for sw in sw_acc_data.keys():
            if sw == AccKeys.RELAY:
                continue
            sw_data = sw_acc_data[sw]
            for acc in sw_data.keys():
                if table_tag == "hidden" and sw_data[acc].get("hidden", None) != True:
                    continue
                if table_tag == "auto_start" and sw_data[acc].get("auto_start", None) != True:
                    continue

                # 账号详情
                details = AccInfoFunc.get_acc_details(sw, acc)
                img = details[AccKeys.AVATAR]
                display_name = details[AccKeys.DISPLAY]
                hotkey = details[AccKeys.HOTKEY]
                hidden = details[AccKeys.HIDDEN]
                auto_start = details[AccKeys.AUTO_START]
                nickname = details[AccKeys.NICKNAME]
                # 对详情数据进行处理
                display_name = "  " + display_name
                hotkey = hotkey if hotkey != "" else "-"
                hidden = "√" if hidden is True else "-"
                auto_start = "√" if auto_start is True else "-"
                nickname = nickname if nickname else "请获取数据"
                img = img.resize(Config.AVT_SIZE, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.photo_images.append(photo)

                # 如果该 sw 节点还没有插入过，先插入它
                if sw not in sw_nodes:
                    # 插入 sw 节点，并保存节点的 ID
                    sw_node_id = tree.insert("", "end", iid=sw,
                                             values=(sw, " ", " ", " ", " ", " "), open=True)
                    sw_nodes[sw] = sw_node_id
                else:
                    # 已经有这个 sw 节点，使用已存储的 ID
                    sw_node_id = sw_nodes[sw]

                try:
                    # 插入 account 数据，作为 sw 节点的子节点
                    tree.insert(sw_node_id, "end", iid=f"{sw}/{acc}", image=photo,
                                values=(display_name, hotkey, hidden, auto_start, acc, nickname))
                except Exception as ec:
                    logger.warning(ec)
                    tree.insert(sw_node_id, "end", iid=f"{sw}/{acc}", image=photo,
                                values=StringUtils.clean_texts(
                                    display_name, hotkey, hidden, auto_start, acc, nickname))

        self.can_quick_refresh = True
        self.parent_class.quick_refresh_mode = True
        self.null_data = True if len(tree.get_children()) == 0 else False

    def click_on_id_column(self, click_time, item_id):
        """
        单击id列时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :return:
        """
        if click_time == 1:
            if len(self.tree.get_children(item_id)) == 0:
                WndCreator.open_acc_detail(item_id, self.parent_class)

    def on_tree_configure(self, event):
        """
        表格配置时，执行的操作
        :param event:
        :return:
        """
        # 在非全屏时，隐藏特定列
        columns_to_hide = ["账号标识", "平台id", "昵称"]
        self.adjust_columns(self.wnd, columns_to_hide)

    def save_col_sort(self):
        table_tag = self.table_tag
        col = self.default_sort["col"]
        is_asc_after = self.default_sort["is_asc"]
        AppFunc.save_a_global_setting_and_callback(f'{table_tag}_sort', f"{col},{is_asc_after}")
