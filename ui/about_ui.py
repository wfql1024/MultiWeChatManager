# about_ui.py
import re
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from functions import func_update, subfunc_file
from resources import Config, Strings
from ui import update_log_ui
from utils import hwnd_utils


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
        text_widget.tag_bind(url, "<Button-1>", lambda e, open_url=url: webbrowser.open_new(open_url))

        # 鼠标进入事件 - 改变鼠标形状为手型
        text_widget.tag_bind(url, "<Enter>", lambda e: text_widget.config(cursor="hand2"))

        # 鼠标离开事件 - 恢复鼠标形状为默认
        text_widget.tag_bind(url, "<Leave>", lambda e: text_widget.config(cursor=""))


class AboutWindow:
    def __init__(self, master, need_to_update):
        self.master = master
        master.title("关于")

        window_width = 600
        window_height = 500
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 禁用窗口大小调整
        master.resizable(False, False)

        # 移除窗口装饰并设置为工具窗口
        master.attributes('-toolwindow', True)
        master.grab_set()

        # 图标框架
        logo_frame = ttk.Frame(master, padding="20")
        logo_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # 内容框架
        content_frame = ttk.Frame(master, padding="5")
        content_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

        # 加载并调整图标
        try:
            icon_image = Image.open(Config.PROJ_ICO_PATH)
            icon_image = icon_image.resize((60, 60))
            self.icon_photo = ImageTk.PhotoImage(icon_image)
            icon_label = ttk.Label(logo_frame, image=self.icon_photo)
            icon_label.image = self.icon_photo
            icon_label.pack(side=tk.TOP)
        except Exception as e:
            print(f"无法加载图标图片: {e}")
            # 如果图标加载失败，仍然继续布局
            icon_label = ttk.Label(logo_frame, text="", font=("", 40))
            icon_label.pack(side=tk.TOP)

        # 标题和版本号框架
        title_version_frame = ttk.Frame(content_frame)
        title_version_frame.pack(fill=tk.X, side=tk.TOP, pady=(30, 0))

        current_full_version = subfunc_file.get_app_current_version()

        # 标题和版本号标签
        title_version_label = ttk.Label(
            title_version_frame,
            text=f"微信多开管理器 {current_full_version}",
            font=("", 12, "bold")
        )
        title_version_label.pack(anchor='w')

        # 开发者主页
        author_label = ttk.Label(content_frame, text="by 吾峰起浪", font=("", 11))
        author_label.pack(anchor='w', pady=(10, 0))
        reference_frame = ttk.Frame(content_frame)
        reference_frame.pack(fill=tk.X)
        pj_home_link = tk.Label(reference_frame, text="吾爱破解主页", font=("", 10), fg="grey", cursor="hand2")
        bilibili_home_link = tk.Label(reference_frame, text="哔哩哔哩主页", font=("", 10), fg="grey", cursor="hand2")
        github_home_link = tk.Label(reference_frame, text="GitHub主页", font=("", 10), fg="grey", cursor="hand2")
        gitee_home_link = tk.Label(reference_frame, text="Gitee主页", font=("", 10), fg="grey", cursor="hand2")
        pj_home_link.grid(row=0, column=0, sticky="w", padx=(0, 10))
        bilibili_home_link.grid(row=0, column=1, sticky="w", padx=(0, 10))
        github_home_link.grid(row=0, column=2, sticky="w", padx=(0, 10))
        gitee_home_link.grid(row=0, column=3, sticky="w", padx=(0, 10))
        pj_home_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.PJ_HOME))
        github_home_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.GITHUB_HOME))
        bilibili_home_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.BILIBILI_HOME))
        gitee_home_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.GITEE_HOME))

        # 项目信息
        proj_label = ttk.Label(content_frame, text="项目信息", font=("", 11))
        proj_label.pack(anchor='w', pady=(10, 0))
        repo_frame = ttk.Frame(content_frame)
        repo_frame.pack(fill=tk.X)
        pj_repo_link = tk.Label(repo_frame, text="吾爱破解", font=("", 10), fg="grey", cursor="hand2")
        github_repo_link = tk.Label(repo_frame, text="GitHub", font=("", 10), fg="grey", cursor="hand2")
        gitee_repo_link = tk.Label(repo_frame, text="Gitee", font=("", 10), fg="grey", cursor="hand2")
        pj_repo_link.grid(row=0, column=0, sticky="w", padx=(0, 10))
        github_repo_link.grid(row=0, column=1, sticky="w", padx=(0, 10))
        gitee_repo_link.grid(row=0, column=2, sticky="w", padx=(0, 10))
        pj_repo_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.PJ_REPO))
        github_repo_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.GITHUB_REPO))
        gitee_repo_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.GITEE_REPO))

        # 鸣谢
        thanks_label = ttk.Label(content_frame, text="鸣谢", font=("", 11))
        thanks_label.pack(anchor='w', pady=(10, 0))
        reference_frame = ttk.Frame(content_frame)
        reference_frame.pack(fill=tk.X)
        link1 = tk.Label(reference_frame, text="lyie15", font=("", 10), fg="grey", cursor="hand2")
        link2 = tk.Label(reference_frame, text="windion", font=("", 10), fg="grey", cursor="hand2")
        link3 = tk.Label(reference_frame, text="Anhkgg", font=("", 10), fg="grey", cursor="hand2")
        link4 = tk.Label(reference_frame, text="de52", font=("", 10), fg="grey", cursor="hand2")
        link5 = tk.Label(reference_frame, text="yihleego", font=("", 10), fg="grey", cursor="hand2")
        link6 = tk.Label(reference_frame, text="cherub0507", font=("", 10), fg="grey", cursor="hand2")
        link1.grid(row=0, column=0, sticky="w", padx=(0, 10))
        link2.grid(row=0, column=1, sticky="w", padx=(0, 10))
        link3.grid(row=0, column=2, sticky="w", padx=(0, 10))
        link4.grid(row=0, column=3, sticky="w", padx=(0, 10))
        link5.grid(row=0, column=4, sticky="w", padx=(0, 10))
        link6.grid(row=0, column=5, sticky="w", padx=(0, 10))
        link1.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.LYIE15_PJ))
        link2.bind("<Button-1>",
                   lambda e: webbrowser.open_new(Strings.WINDION_PJ) and webbrowser.open_new(Strings.WINDION_BILIBILI))
        link3.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.ANHKGG_GITHUB))
        link4.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.DE52_PJ))
        link5.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.YIHLEEGO_GITHUB))
        link6.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.CHERUB0507_PJ))

        # 技术参考(标题)
        reference_label = ttk.Label(content_frame, text="技术参考", font=("", 11))
        reference_label.pack(anchor='w', pady=(10, 0))

        # 底部区域=声明+检查更新按钮
        update_text = "检查更新"
        if need_to_update:
            update_text = "✨检查更新"
        bottom_frame = ttk.Frame(content_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
        disclaimer_frame = ttk.Frame(bottom_frame)
        disclaimer_frame.pack(side=tk.LEFT)
        update_button = ttk.Button(bottom_frame, text=update_text,
                                   command=partial(self.check_for_updates,
                                                   current_full_version=current_full_version))
        update_button.pack(side=tk.RIGHT)

        # 免责声明
        style = ttk.Style()
        style.configure("RedWarning.TLabel", foreground="red", font=("", 8))
        disclaimer_label = ttk.Label(disclaimer_frame, text="仅供学习交流，严禁用于商业用途，请于24小时内删除",
                                     style="RedWarning.TLabel")
        disclaimer_label.pack(side=tk.BOTTOM, pady=(8, 0))

        # 版权信息标签
        copyright_label = ttk.Label(
            disclaimer_frame,
            text="Copyright © 2024 吾峰起浪. All rights reserved.",
            font=("", 8)
        )
        copyright_label.pack(side=tk.TOP, pady=(5, 0))

        # 创建一个用于放置滚动文本框的框架
        reference_frame = ttk.Frame(content_frame)
        reference_frame.pack(pady=(5, 0), fill=tk.BOTH, expand=True)

        # 创建滚动条
        scrollbar = tk.Scrollbar(reference_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建不可编辑且可滚动的文本框
        reference_text = tk.Text(reference_frame, wrap=tk.WORD, font=("", 8), height=6, bg=master.cget("bg"),
                                 yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        # 插入文本并为URL添加标签
        reference_text.insert(tk.END, Strings.REFERENCE_TEXT)
        add_hyperlink_events(reference_text, Strings.REFERENCE_TEXT)

        # 设置文本框为不可编辑
        reference_text.config(state=tk.DISABLED)
        reference_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 配置滚动条
        scrollbar.config(command=reference_text.yview)

    def check_for_updates(self, current_full_version):
        subfunc_file.fetch_config_data_from_remote()
        result = func_update.split_vers_by_cur_from_local(current_full_version)
        if result:
            new_versions, old_versions = result
            if len(new_versions) != 0:
                update_log_window = tk.Toplevel(self.master)
                update_log_ui.UpdateLogWindow(update_log_window, old_versions, new_versions)
            else:
                messagebox.showinfo("提醒", f"当前版本{current_full_version}已是最新版本。")
                return True
        else:
            messagebox.showinfo("错误", f"获取失败。")
            return False


if __name__ == '__main__':
    root = tk.Tk()
    about_window = AboutWindow(root)
    root.mainloop()
