import tkinter as tk
from abc import ABC

from PIL import Image, ImageTk

from functions import subfunc_file, func_account
from public_class import reusable_widget
from resources import Constants, Config
from utils import hwnd_utils, string_utils, json_utils
from utils.logger_utils import mylogger as logger


class AccManagerWindow:
    def __init__(self, parent_class, wnd, sw):
        self.acc_data = None
        self.tree_class = {}

        self.parent_class = parent_class
        self.root_class = self.parent_class.root_class
        self.root = self.parent_class.root
        self.wnd = wnd
        self.sw = sw
        self.wnd.title(f"账号管理")
        self.wnd.attributes('-toolwindow', True)
        self.window_width, self.window_height = Constants.ACC_MNG_WND_SIZE
        hwnd_utils.bring_tk_wnd_to_center(self.wnd, self.window_width, self.window_height)
        wnd.grab_set()
        wnd.update_idletasks()

        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widget.ScrollableCanvas(wnd)
        self.main_frame = self.scrollable_canvas.main_frame

        self.btn_dict = {
            "cancel_hiding_btn": {
                "text": "取消隐藏",
                "btn": None,
                "func": self.to_cancel_hiding_of_,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要取消隐藏的账号": [(0, 0)]
                }
            },
            "cancel_auto_start_btn": {
                "text": "取消自启",
                "btn": None,
                "func": self.to_cancel_auto_start_of_,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要取消自启的账号": [(0, 0)]
                },
            },
            "add_hiding_btn": {
                "text": "隐藏",
                "btn": None,
                "tip": "请选择要隐藏的账号",
                "func": self.to_add_hiding_of_,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要隐藏的账号": [(0, 0)]
                },
            },
            "add_auto_start_btn": {
                "text": "自启",
                "btn": None,
                "tip": "请选择要自启的账号",
                "func": self.to_add_auto_start_of_,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要自启的账号": [(0, 0)]
                },
            },
            "add_hotkey_btn": {
                "text": "添加热键",
                "btn": None,
                "tip": "请选择一个要添加热键的账号",
                "func": self.to_add_hotkey_of_,
                "enable_scopes": [(1, 1)],
                "tip_scopes_dict": {
                    "请选择一个要添加热键的账号": [(0, 0)]
                },
            }
        }
        self.display_ui()

    def display_ui(self):
        self.acc_data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
        # 加载已隐藏列表
        self.tree_class["hidden"] = AccManageTreeView(
            self,
            "hidden", "已隐藏：", self.btn_dict["cancel_hiding_btn"],
        )
        # 加载已自启列表
        self.tree_class["auto_start"] = AccManageTreeView(
            self, "auto_start", "已自启：", self.btn_dict["cancel_auto_start_btn"])
        # 加载所有
        self.tree_class["all"] = AccManageTreeView(
            self, "all", "所有账号：", None,
            self.btn_dict["add_auto_start_btn"],
            self.btn_dict["add_hiding_btn"],
        )

        # 加载完成后更新一下界面并且触发事件
        self.scrollable_canvas.refresh_canvas()

    def to_cancel_hiding_of_(self, items):
        print(f"进入取消隐藏方法")
        for item in items:
            sw, acc = item.split("/")
            subfunc_file.update_sw_acc_details_to_json(sw, acc, hidden=False)
        self.refresh_acc_manager()
        pass

    def to_cancel_auto_start_of_(self, items):
        print(f"进入取消自启方法")
        for item in items:
            sw, acc = item.split("/")
            subfunc_file.update_sw_acc_details_to_json(sw, acc, auto_start=False)
        self.refresh_acc_manager()
        pass

    def to_add_hiding_of_(self, items):
        print(f"进入隐藏方法")
        for item in items:
            sw, acc = item.split("/")
            subfunc_file.update_sw_acc_details_to_json(sw, acc, hidden=True)
        self.refresh_acc_manager()
        pass

    def to_add_auto_start_of_(self, items):
        print(f"进入自启方法")
        for item in items:
            sw, acc = item.split("/")
            subfunc_file.update_sw_acc_details_to_json(sw, acc, auto_start=True)
        self.refresh_acc_manager()
        pass

    def to_add_hotkey_of_(self, items):
        print(f"进入添加热键方法")
        pass

    def refresh_acc_manager(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.display_ui()


class AccManageTreeView(reusable_widget.ActionableTreeView, ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.acc_data = None
        self.wnd = None
        self.photo_images = []
        self.sign_visible = None
        self.data_dir = None
        super().__init__(parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.wnd = self.parent_class.wnd
        # print(f"self.wnd={self.wnd}")
        self.acc_data = self.parent_class.acc_data
        self.data_dir = self.root_class.sw_info["data_dir"]
        self.sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default("sign_visible") == "True"
        self.columns = (" ", "快捷键", "隐藏", "自启动", "原始id", "昵称")
        sort_str = subfunc_file.fetch_global_setting_or_set_default(f"{self.table_tag}_sort")
        self.default_sort["col"], self.default_sort["is_asc"] = sort_str.split(",")

    def set_table_style(self):
        super().set_table_style()

        tree = self.tree
        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Constants.COLUMN_MIN_WIDTH["SEC_ID"],
                    width=Constants.COLUMN_WIDTH["SEC_ID"], stretch=tk.NO)
        tree.column(" ", minwidth=Constants.COLUMN_MIN_WIDTH["展示"],
                    width=Constants.COLUMN_WIDTH["展示"], anchor='w')
        tree.column("快捷键", minwidth=Constants.COLUMN_MIN_WIDTH["快捷键"],
                    width=Constants.COLUMN_WIDTH["快捷键"], anchor='center', stretch=tk.NO)
        tree.column("自启动", minwidth=Constants.COLUMN_MIN_WIDTH["自启动"],
                    width=Constants.COLUMN_WIDTH["自启动"], anchor='w', stretch=tk.NO)
        tree.column("隐藏", minwidth=Constants.COLUMN_MIN_WIDTH["隐藏"],
                    width=Constants.COLUMN_WIDTH["隐藏"], anchor='center', stretch=tk.NO)
        tree.column("原始id", anchor='center')
        tree.column("昵称", anchor='center')

        # 在非全屏时，隐藏特定列
        columns_to_hide = ["原始id", "当前id", "昵称"]
        col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        self.tree.bind("<Configure>", lambda e: self.adjust_columns_on_maximize_(
            e, self.wnd, col_width_to_show, columns_to_hide), add='+')

    def display_table(self):
        tree = self.tree.nametowidget(self.tree)
        sw_acc_data = self.acc_data
        table_tag = self.table_tag

        # 假设你已经有了一个用于存储 sw 节点的字典
        sw_nodes = {}

        for sw in sw_acc_data.keys():
            sw_data = sw_acc_data[sw]
            for acc in sw_data.keys():
                if acc == "all_acc":
                    continue
                if table_tag == "hidden" and sw_data[acc].get("hidden", None) != True:
                    continue
                if table_tag == "auto_start" and sw_data[acc].get("auto_start", None)!= True:
                    continue

                display_name = "  " + func_account.get_acc_origin_display_name(sw, acc)
                avatar_url, hotkey, hidden, auto_start, nickname = subfunc_file.get_sw_acc_details_from_json(
                    sw,
                    acc,
                    avatar_url=None,
                    hotkey="-",
                    hidden="-",
                    auto_start="-",
                    nickname="请获取数据",
                )

                # 获取头像图像
                img = func_account.get_acc_avatar_from_files(acc, sw)
                img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
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
                                values=string_utils.clean_texts(
                                    display_name, hotkey, hidden, auto_start, acc, nickname))

    def adjust_columns_on_maximize_(self, event, wnd, col_width_to_show, columns_to_hide=None):
        # print("触发列宽调整")
        tree = self.tree.nametowidget(event.widget)

        if wnd.state() != "zoomed":
            # 非最大化时隐藏列和标题
            tree["show"] = "tree headings"  # 隐藏标题
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

class AccEntity:
    def __init__(self, sw, acc):
        self.sw = sw
        self.acc = acc
    pass