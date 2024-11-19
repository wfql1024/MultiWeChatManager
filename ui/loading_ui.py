from tkinter import ttk


class LoadingWindow:
    def __init__(self, master):
        # print("打开加载窗口")
        self.master = master
        self.master.title("加载中")
        self.label = ttk.Label(self.master, text="正在载入，请稍等……")
        self.label.pack(pady=20)
        self.progress = ttk.Progressbar(self.master, mode="determinate", length=250)
        self.progress.pack(pady=10)

        self.master.withdraw()  # 初始时隐藏窗口
        window_width = 300
        window_height = 100
        # 计算窗口位置
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.master.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.master.resizable(False, False)
        # print("显示等待窗口")
        self.master.deiconify()  # 显示窗口
        self.progress.start(15)

    def destroy(self):
        if self.master.winfo_exists():
            self.progress.stop()
            self.progress['value'] = self.progress['maximum']
            self.master.update_idletasks()
            self.master.destroy()
