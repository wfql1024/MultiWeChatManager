# about_ui.py
import re
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from functions import func_update, subfunc_file
from resources import Config, Strings, Constants
from ui import update_log_ui
from utils import hwnd_utils, widget_utils


def add_hyperlink_events(text_widget, text_content):
    """为文本框中的URL添加点击事件，并在鼠标移动到链接时变成手型"""
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


def open_url(url):
    if url is None or url == "":
        return
    webbrowser.open_new(url)


class AboutWindow:
    def __init__(self, root, parent, wnd, need_to_update):
        self.root = root
        self.parent = parent
        self.wnd = wnd
        self.wnd.title("关于")
        self.width, self.height = Constants.ABOUT_WND_SIZE
        hwnd_utils.bring_wnd_to_center(self.wnd, self.width, self.height)

        # 禁用窗口大小调整
        self.wnd.resizable(False, False)

        # 移除窗口装饰并设置为工具窗口
        self.wnd.attributes('-toolwindow', True)
        self.wnd.grab_set()

        # 图标框架
        logo_frame = ttk.Frame(self.wnd, padding=Constants.LOGO_FRM_PAD)
        logo_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # 内容框架
        content_frame = ttk.Frame(self.wnd, padding=Constants.CONTENT_FRM_PAD)
        content_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

        # 加载并调整图标
        try:
            icon_image = Image.open(Config.PROJ_ICO_PATH)
            icon_image = icon_image.resize(Constants.LOGO_SIZE, Image.LANCZOS)
            self.icon_photo = ImageTk.PhotoImage(icon_image)
        except Exception as e:
            print(f"无法加载图标图片: {e}")
            # 如果图标加载失败，仍然继续布局
            self.icon_photo = ImageTk.PhotoImage(Image.new('RGB', Constants.BLANK_LOGO_SIZE, color='white'))
        icon_label = ttk.Label(logo_frame, image=self.icon_photo)
        icon_label.image = self.icon_photo
        icon_label.pack(side=tk.TOP)

        # 标题和版本号框架
        title_version_frame = ttk.Frame(content_frame)
        title_version_frame.pack(fill=tk.X, side=tk.TOP, pady=Constants.VER_FRM_PAD_Y)

        current_full_version = subfunc_file.get_app_current_version()

        # 标题和版本号标签
        title_version_label = ttk.Label(
            title_version_frame,
            text=f"微信多开管理器 {current_full_version}",
            style='FirstTitle.TLabel',
        )
        title_version_label.pack(anchor='w')

        # 开发者主页
        author_label = ttk.Label(content_frame, text="by 吾峰起浪", style='SecondTitle.TLabel')
        author_label.pack(anchor='w', pady=Constants.SECOND_TITLE_PAD_Y)
        author_frame = ttk.Frame(content_frame)
        author_frame.pack(fill=tk.X)
        row = 0
        for idx, (text, url) in enumerate(Strings.AUTHOR.items()):
            link = ttk.Label(author_frame, text=text,
                             style="Link.TLabel", cursor="hand2")
            link.grid(row=row, column=idx, sticky="w", padx=Constants.ABOUT_GRID_PAD_X)
            # 绑定点击事件
            link.bind("<Button-1>", lambda event, url2open=url: open_url(url2open))

        # 项目信息
        proj_label = ttk.Label(content_frame, text="项目信息", style='SecondTitle.TLabel')
        proj_label.pack(anchor='w', pady=Constants.SECOND_TITLE_PAD_Y)
        proj_frame = ttk.Frame(content_frame)
        proj_frame.pack(fill=tk.X)
        row = 0
        for idx, (text, url) in enumerate(Strings.PROJ.items()):
            link = ttk.Label(proj_frame, text=text,
                             style="Link.TLabel", cursor="hand2")
            link.grid(row=row, column=idx, sticky="w", padx=Constants.ABOUT_GRID_PAD_X)
            # 绑定点击事件
            link.bind("<Button-1>", lambda event, url2open=url: open_url(url2open))

        # 鸣谢
        thanks_label = ttk.Label(content_frame, text="鸣谢", style='SecondTitle.TLabel')
        thanks_label.pack(anchor='w', pady=Constants.SECOND_TITLE_PAD_Y)
        thanks_frame = ttk.Frame(content_frame)
        thanks_frame.pack(fill=tk.X)
        row = 0
        for idx, (person, info) in enumerate(Strings.THANKS.items()):
            link = ttk.Label(thanks_frame, text=info.get('text', None),
                             style="Link.TLabel", cursor="hand2")
            link.grid(row=row, column=idx, sticky="w", padx=Constants.ABOUT_GRID_PAD_X)
            # 绑定点击事件
            link.bind(
                "<Button-1>",
                lambda
                    event,
                    bilibili=info.get('bilibili', None),
                    github=info.get('github', None),
                    pj=info.get('52pj', None) :
                (
                    open_url(bilibili),
                    open_url(github),
                    open_url(pj)
                )
            )

        # 底部区域=声明+检查更新按钮
        update_text = "检查更新"
        if need_to_update:
            update_text = "✨检查更新"
        bottom_frame = ttk.Frame(content_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X,
                          padx=Constants.ABOUT_BTM_FRM_PAD_X, pady=Constants.ABOUT_BTM_FRM_PAD_Y)
        disclaimer_frame = ttk.Frame(bottom_frame)
        disclaimer_frame.pack(side=tk.LEFT)
        update_button = ttk.Button(bottom_frame, text=update_text, style='Custom.TButton',
                                   command=partial(self.check_for_updates,
                                                   current_full_version=current_full_version))
        update_button.pack(side=tk.RIGHT)

        # 免责声明
        disclaimer_label = ttk.Label(disclaimer_frame, style="RedWarning.TLabel",
                                     text="仅供学习交流，严禁用于商业用途，请于24小时内删除")
        disclaimer_label.pack(side=tk.BOTTOM)

        # 版权信息标签
        copyright_label = ttk.Label(
            disclaimer_frame,
            text="Copyright © 2024 吾峰起浪. All rights reserved.",
            style="LittleText.TLabel",
        )
        copyright_label.pack(side=tk.TOP)

        # 技术参考
        reference_label = ttk.Label(content_frame, text="技术参考", style='SecondTitle.TLabel')
        reference_label.pack(anchor='w', pady=Constants.SECOND_TITLE_PAD_Y)
        reference_frame = ttk.Frame(content_frame)
        reference_frame.pack(fill=tk.BOTH, expand=True)
        reference_scrollbar = tk.Scrollbar(reference_frame)
        reference_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        reference_text = tk.Text(reference_frame, wrap=tk.WORD, font=("", Constants.LITTLE_FONTSIZE),
                                 height=8, bg=wnd.cget("bg"),
                                 yscrollcommand=reference_scrollbar.set, bd=0, highlightthickness=0)

        reference_text.insert(tk.END, '\n')
        reference_text.insert(tk.END, Strings.REFERENCE_TEXT)
        reference_text.insert(tk.END, '\n')

        add_hyperlink_events(reference_text, Strings.REFERENCE_TEXT)
        reference_text.config(state=tk.DISABLED)
        reference_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=Constants.ABOUT_GRID_PAD_X)
        reference_scrollbar.config(command=reference_text.yview)
        self.reference_scroll_task = widget_utils.auto_scroll_text(reference_text, self.root)

        # 赞助
        sponsor_label = ttk.Label(content_frame, text="赞助", style='SecondTitle.TLabel')
        sponsor_label.pack(anchor='w', pady=Constants.SECOND_TITLE_PAD_Y)
        sponsor_frame = ttk.Frame(content_frame)
        sponsor_frame.pack(fill=tk.BOTH, expand=True)
        sponsor_scrollbar = tk.Scrollbar(sponsor_frame)
        sponsor_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        sponsor_text = tk.Text(sponsor_frame, wrap=tk.WORD, font=("", Constants.LITTLE_FONTSIZE),
                                 height=3, bg=wnd.cget("bg"), foreground='grey',
                                 yscrollcommand=sponsor_scrollbar.set, bd=0, highlightthickness=0)

        sponsor_list = Strings.SPONSOR_TEXT
        sponsor_list_lines = []
        for idx, item in enumerate(sponsor_list):
            date = sponsor_list[idx].get('date', None)
            currency = sponsor_list[idx].get('currency', None)
            amount = sponsor_list[idx].get('amount', None)
            user = sponsor_list[idx].get('user', None)
            sponsor_list_lines.append(f"• {date}  {currency}{amount}  {user}")
        sponsor_text.insert(tk.END, '\n')
        sponsor_text.insert(tk.END, '\n'.join(sponsor_list_lines))
        sponsor_text.insert(tk.END, '\n')
        sponsor_text.config(state=tk.DISABLED)
        sponsor_text.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=Constants.ABOUT_GRID_PAD_X)
        sponsor_scrollbar.config(command=sponsor_text.yview)
        self.sponsor_scroll_task = widget_utils.auto_scroll_text(sponsor_text, self.root)

    def check_for_updates(self, current_full_version):
        subfunc_file.fetch_and_decrypt_config_data_from_remote()
        success, result = func_update.split_vers_by_cur_from_local(current_full_version)
        if success is True:
            new_versions, old_versions = result
            if len(new_versions) != 0:
                update_log_window = tk.Toplevel(self.wnd)
                update_log_ui.UpdateLogWindow(update_log_window, old_versions, new_versions)
            else:
                messagebox.showinfo("提醒", f"当前版本{current_full_version}已是最新版本。")
                return True
        else:
            messagebox.showinfo("错误", result)
            return False


if __name__ == '__main__':
    test_root = tk.Tk()
    about_window = AboutWindow(test_root, test_root, test_root, True)
    test_root.mainloop()
