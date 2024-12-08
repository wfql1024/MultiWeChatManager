from tkinter import ttk
from resources import Constants
from utils import hwnd_utils


class LoadingWindow:
    def __init__(self, wnd):
        # print("打开加载窗口")
        self.wnd = wnd
        self.wnd.title("加载中")
        self.label = ttk.Label(self.wnd, text="正在载入，请稍等……")
        self.label.pack(pady=20)
        self.progress = ttk.Progressbar(self.wnd, mode="determinate", length=250)
        self.progress.pack(pady=10)

        self.wnd.withdraw()  # 初始时隐藏窗口
        wnd_width, wnd_height = Constants.LOADING_WND_SIZE
        hwnd_utils.bring_wnd_to_center(self.wnd, wnd_width, wnd_height)

        self.wnd.resizable(False, False)
        # print("显示等待窗口")
        self.wnd.deiconify()  # 显示窗口
        self.progress.start(15)

    def auto_close(self):
        if self.wnd.winfo_exists():
            self.progress.stop()
            self.progress['value'] = self.progress['maximum']
            self.wnd.update_idletasks()
            self.wnd.destroy()
