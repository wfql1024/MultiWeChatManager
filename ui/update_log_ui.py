import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from functions import func_update
from resources import Config
from utils import handle_utils


class UpdateLogWindow:
    def __init__(self, master, old_versions, new_versions=None):
        self.master = master
        master.title("版本日志" if not new_versions else "发现新版本")

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
        master.overrideredirect(True)
        master.overrideredirect(False)
        master.attributes('-toolwindow', True)

        main_frame = ttk.Frame(master, padding="5")
        main_frame.pack(fill="both", expand=True)

        # 更新日志(标题)
        log_label = ttk.Label(main_frame, text="更新日志", font=("", 11))
        log_label.pack(anchor='w', pady=(10, 0))

        print("显示更新日志")

        # 底部区域=声明+检查更新按钮
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
        cancel_button = ttk.Button(bottom_frame, text="以后再说",
                                   command=lambda: self.master.destroy())
        cancel_button.pack(side=tk.RIGHT)
        download_button = ttk.Button(bottom_frame, text="下载新版",
                                     command=self.show_download_window)
        download_button.pack(side=tk.RIGHT)

        # 说明
        information_label = ttk.Label(
            bottom_frame,
            text="发现新版本，是否下载？"
        )
        information_label.pack(side=tk.RIGHT, pady=(5, 0))

        # 创建一个用于放置滚动文本框的框架
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(pady=(5, 0), fill=tk.BOTH, expand=True)

        # 创建滚动条
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建不可编辑且可滚动的文本框
        log_text = tk.Text(log_frame, wrap=tk.WORD, font=("", 8), height=6, bg=master.cget("bg"),
                           yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        if new_versions:
            log_text.insert(tk.END, new_versions)
            log_text.insert(tk.END, "\n")
        # 插入文本并为URL添加标签
        log_text.insert(tk.END, old_versions)

        # 设置文本框为不可编辑
        log_text.config(state=tk.DISABLED)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 配置滚动条
        scrollbar.config(command=log_text.yview)

    def show_download_window(self, file_urls, temp_dir):
        temp_dir = tempfile.mkdtemp()
        file_url = f"https://d.feijix.com/storage/files/2024/10/06/6/10172646/17281995030431.gz?t=67052ac9&rlimit=20&us=Ioo2xfdKuS&sign=e813036e84770a466a9686509c3f10a5&download_name=MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
        # file_url = f"https://gitee.com/wfql1024/MultiWeChatManagerDist/raw/master/MultiWeChatManager_x64_v{latest_version[1]}.zip"
        file_urls = [file_url]  # 更新文件列表
        self.show_download_window(file_urls, temp_dir)
        download_window = tk.Toplevel(self.master)
        download_window.title("下载更新")
        handle_utils.center_window(download_window)

        global progress_var, progress_bar
        progress_var = tk.StringVar(value="开始下载...")
        tk.Label(download_window, textvariable=progress_var).pack(pady=10)

        progress_bar = ttk.Progressbar(download_window, orient="horizontal", length=300, mode="determinate")
        progress_bar.pack(pady=10)

        tk.Button(download_window, text="关闭并更新",
                  # command=lambda: start_update_process(temp_dir)
                  ).pack(pady=10)

        # 开始下载文件（多线程）
        threading.Thread(target=func_update.download_files, args=(file_urls, temp_dir, self.update_progress)).start()

    def update_progress(self, idx, total_files, downloaded, total_length):
        percentage = (downloaded / total_length) * 100 if total_length else 0
        progress_var.set(f"下载文件 {idx + 1}/{total_files}: {percentage:.2f}% 完成")
        progress_bar['value'] = percentage
        self.master.update_idletasks()

# if __name__ == "__main__":
#     root = tk.Tk()
#     update_log_window = UpdateLogWindow(root, 'old')
#     root.mainloop()
