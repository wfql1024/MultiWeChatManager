# about_ui.py
import tkinter as tk
import webbrowser
from abc import ABC
from functools import partial
from tkinter import ttk, messagebox
from typing import Dict, Union

from PIL import Image, ImageTk

from functions import func_update, subfunc_file
from public_class.enums import Keywords
from public_class.reusable_widget import SubToolWnd
from resources import Config, Strings, Constants
from ui import update_log_ui
from utils import widget_utils
from utils.logger_utils import mylogger as logger


class Direction:
    def __init__(self, initial=1):
        self.value = initial


def open_urls(urls):
    if urls is None:
        return
    url_list = list(urls)
    if len(url_list) == 0:
        return
    for url in url_list:
        webbrowser.open_new(url)


def pack_grids(frame, part_dict, max_columns=6):
    grids = ttk.Frame(frame)
    grids.pack(**Constants.T_FRM_PACK)
    for idx, info in enumerate(part_dict.values()):
        item = ttk.Label(grids, text=info.get('text', None),
                         style="Link.TLabel", cursor="hand2")
        row = idx // max_columns
        column = idx % max_columns
        item.grid(row=row, column=column, **Constants.W_GRID_PACK)

        # 获取所有链接
        urls = []
        for link in info["links"].values():
            urls.append(link)

        # 绑定点击事件
        item.bind("<Button-1>", partial(lambda event, urls2open: open_urls(urls2open), urls2open=urls))


class AboutWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, app_info):
        self.logo_img = None
        self.scroll_text_str = None
        self.scroll_direction = None
        self.scroll_tasks = None
        self.remote_cfg_data = None
        self.about_info = None
        self.app_name = None
        self.content_frame = None
        self.main_frame = None

        self.app_info = app_info

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.ABOUT_WND_SIZE
        self.scroll_tasks: Dict[str, Union[list, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.scroll_direction: Dict[str, Union[Direction, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.scroll_text_str: Dict[str, Union[str, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.logo_img = []


    def set_wnd(self):
        self.wnd.resizable(False, False)

    def load_content(self):
        self.remote_cfg_data = subfunc_file.read_remote_cfg_in_rules()
        if self.remote_cfg_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            # 关闭wnd窗口
            self.wnd.destroy()
        else:
            self.display_main_content()

    def display_main_content(self):
        self.app_name = self.remote_cfg_data[Keywords.GLOBAL_SECTION]["app_name"]
        self.about_info = self.remote_cfg_data[Keywords.GLOBAL_SECTION]["about"]

        self.main_frame = ttk.Frame(self.wnd, padding=Constants.FRM_PAD)
        self.main_frame.pack(**Constants.FRM_PACK)

        # 图标框架（左框架）
        logo_frame = ttk.Frame(self.main_frame, padding=Constants.L_FRM_PAD)
        logo_frame.pack(**Constants.L_FRM_PACK)

        # 内容框架（右框架）
        self.content_frame = ttk.Frame(self.main_frame, padding=Constants.R_FRM_PAD)
        self.content_frame.pack(**Constants.R_FRM_PACK)

        # 加载并调整图标
        try:
            icon_image = Image.open(Config.PROJ_ICO_PATH)
            icon_image = icon_image.resize(Constants.LOGO_SIZE, Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(icon_image)
        except Exception as e:
            logger.error(f"无法加载图标图片: {e}")
            # 如果图标加载失败，仍然继续布局
            self.logo_img = ImageTk.PhotoImage(Image.new('RGB', Constants.LOGO_SIZE, color='white'))
        icon_label = ttk.Label(logo_frame, image=self.logo_img)
        icon_label.image = self.logo_img
        icon_label.pack(**Constants.T_WGT_PACK)

        # 顶部：标题和版本号框架
        title_version_frame = ttk.Frame(self.content_frame)
        title_version_frame.pack(**Constants.T_FRM_PACK)

        # 标题和版本号标签
        current_full_version = subfunc_file.get_app_current_version()
        title_version_str = f"{self.app_name} {current_full_version}"
        title_version_label = ttk.Label(
            title_version_frame,
            text=title_version_str,
            style='FirstTitle.TLabel',
        )
        title_version_label.pack(anchor='sw', **Constants.T_WGT_PACK, ipady=Constants.IPAD_Y)

        # 开发者主页
        author_label = ttk.Label(self.content_frame, text="by 吾峰起浪", style='SecondTitle.TLabel')
        author_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        pack_grids(self.content_frame, self.about_info["author"])

        # 项目信息
        proj_label = ttk.Label(self.content_frame, text="项目信息", style='SecondTitle.TLabel')
        proj_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        pack_grids(self.content_frame, self.about_info["project"])

        # 鸣谢
        thanks_label = ttk.Label(self.content_frame, text="鸣谢", style='SecondTitle.TLabel')
        thanks_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        pack_grids(self.content_frame, self.about_info["thanks"])

        # 技术参考
        reference_label = ttk.Label(self.content_frame, text="技术参考", style='SecondTitle.TLabel')
        reference_label.pack(anchor='w', **Constants.T_WGT_PACK)
        reference_frame = ttk.Frame(self.content_frame)
        reference_frame.pack(**Constants.T_FRM_PACK)

        reference_list = self.about_info.get('reference', [])
        lines = []
        for item in reference_list:
            lines.append(item["title"])
            lines.append(item["link"])
            lines.append("")  # 空行
        self.scroll_text_str["reference"] = "\n".join(lines).strip()

        self.pack_scrollable_text(reference_frame, "reference", 12)

        # 赞助
        sponsor_label = ttk.Label(self.content_frame, text="赞助", style='SecondTitle.TLabel')
        sponsor_frame = ttk.Frame(self.content_frame)
        sponsor_label.pack(anchor='w', **Constants.T_WGT_PACK)
        sponsor_frame.pack(**Constants.T_FRM_PACK)

        sponsor_list = self.about_info.get('sponsor', [])
        sponsor_list_lines = []
        for idx, item in enumerate(sponsor_list):
            date = sponsor_list[idx].get('date', None)
            currency = sponsor_list[idx].get('currency', None)
            amount = sponsor_list[idx].get('amount', None)
            user = sponsor_list[idx].get('user', None)
            sponsor_list_lines.append(f"• {date}  {currency}{amount}  {user}")
        self.scroll_text_str["sponsor"] = "\n".join(sponsor_list_lines)

        self.pack_scrollable_text(sponsor_frame, "sponsor", 5)

        # 底部区域=声明+检查更新按钮
        bottom_frame = ttk.Frame(self.content_frame)
        bottom_frame.pack(**Constants.B_FRM_PACK)

        surprise_sign = Strings.SURPRISE_SIGN
        prefix = surprise_sign if self.app_info.need_update is True else ""

        # 左边：声明框架
        disclaimer_frame = ttk.Frame(bottom_frame, padding=Constants.L_FRM_PAD)
        disclaimer_frame.pack(**Constants.L_FRM_PACK)
        # 右边：更新按钮
        update_button = ttk.Button(bottom_frame, text=f"{prefix}检查更新", style='Custom.TButton',
                                   command=partial(self.check_for_updates,
                                                   current_full_version=current_full_version))
        update_button.pack(side=tk.RIGHT)

        # 免责声明
        disclaimer_label = ttk.Label(disclaimer_frame, style="RedWarning.TLabel",
                                     text="仅供学习交流，严禁用于商业用途，请于24小时内删除")
        disclaimer_label.pack(**Constants.B_WGT_PACK)

        # 版权信息标签
        copyright_label = ttk.Label(
            disclaimer_frame,
            text="Copyright © 2024 吾峰起浪. All rights reserved.",
            style="LittleText.TLabel",
        )
        copyright_label.pack(**Constants.T_WGT_PACK)

    def pack_scrollable_text(self, frame, part, height):
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(frame, wrap=tk.WORD, font=("", Constants.LITTLE_FONTSIZE),
                       height=height, bg=self.wnd.cget("bg"),
                       yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        text.insert(tk.END, '\n')
        text.insert(tk.END, self.scroll_text_str[part])
        text.insert(tk.END, '\n')

        widget_utils.add_hyperlink_events(text, self.scroll_text_str[part])
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=Constants.GRID_PAD)
        scrollbar.config(command=text.yview)
        # 创建方向对象
        self.scroll_direction[part] = Direction(1)  # 初始方向为向下
        self.scroll_tasks[part] = []
        # 启动滚动任务
        widget_utils.auto_scroll_text(
            self.scroll_tasks[part], self.scroll_direction[part], text, self.root
        )
        # 鼠标进入控件时取消所有任务
        text.bind(
            "<Enter>",
            lambda event: [
                self.root.after_cancel(task) for task in self.scroll_tasks[part]
            ]
        )
        # 鼠标离开控件时继续滚动，保留当前方向
        text.bind(
            "<Leave>",
            lambda event: widget_utils.auto_scroll_text(
                self.scroll_tasks[part], self.scroll_direction[part], text, self.root
            )
        )

    def check_for_updates(self, current_full_version):
        config_data = subfunc_file.force_fetch_remote_encrypted_cfg()
        if config_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            return False
        success, result = func_update.split_vers_by_cur_from_local(current_full_version)
        if success is True:
            new_versions, old_versions = result
            if len(new_versions) != 0:
                update_log_window = tk.Toplevel(self.wnd)
                update_log_ui.UpdateLogWnd(update_log_window, "", old_versions, new_versions)
            else:
                messagebox.showinfo("提醒", f"当前版本{current_full_version}已是最新版本。")
                return True
        else:
            messagebox.showinfo("错误", result)
            return False

    def finally_do(self):
        for info in self.scroll_tasks.values():
            for task in info:
                try:
                    self.root.after_cancel(task)  # 取消滚动任务
                except Exception as e:
                    logger.error(f"Error cancelling task: {e}")