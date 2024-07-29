import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import get_path_of_data
import get_path_of_wechat


class PathSettingWindow:
    def __init__(self, master, on_close_callback=None):
        self.master = master
        self.on_close_callback = on_close_callback
        master.title("设置路径")

        window_width = 900
        window_height = 180
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 移除窗口装饰并设置为工具窗口
        master.overrideredirect(True)
        master.overrideredirect(False)
        master.attributes('-toolwindow', True)

        master.grab_set()

        # 第一行 - 微信安装路径
        self.install_label = tk.Label(master, text="微信安装路径：")
        self.install_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.install_path_var = tk.StringVar()
        self.install_path_entry = tk.Entry(master, textvariable=self.install_path_var, state='readonly', width=70)
        self.install_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")

        self.install_get_button = ttk.Button(master, text="获取", command=self.get_install_path)
        self.install_get_button.grid(row=0, column=2, padx=5, pady=5)

        self.install_choose_button = ttk.Button(master, text="选择路径", command=self.choose_install_path)
        self.install_choose_button.grid(row=0, column=3, padx=5, pady=5)

        # 第二行 - 微信数据存储路径
        self.data_label = tk.Label(master, text="数据存储路径：")
        self.data_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.data_path_var = tk.StringVar()
        self.data_path_entry = tk.Entry(master, textvariable=self.data_path_var, state='readonly', width=70)
        self.data_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")

        self.data_get_button = ttk.Button(master, text="获取", command=self.get_data_path)
        self.data_get_button.grid(row=1, column=2, padx=5, pady=5)

        self.data_choose_button = ttk.Button(master, text="选择路径", command=self.choose_data_path)
        self.data_choose_button.grid(row=1, column=3, padx=5, pady=5)

        # 添加确定按钮
        self.ok_button = ttk.Button(master, text="确定", command=self.on_ok)
        self.ok_button.grid(row=2, column=3, padx=5, pady=10, sticky="se")

        # 配置列的权重，使得中间的 Entry 可以自动扩展
        master.grid_columnconfigure(1, weight=1)

        # 初始获取路径
        self.get_install_path()
        self.get_data_path()

    def on_ok(self):
        if self.validate_paths():
            if self.on_close_callback:
                self.on_close_callback()
            self.master.destroy()

    def validate_paths(self):
        install_path = self.install_path_var.get()
        data_path = self.data_path_var.get()
        if "获取失败" in install_path or "获取失败" in data_path:
            messagebox.showerror("错误", "请确保两个路径都已正确设置")
            return False
        return True

    def get_install_path(self):
        path = get_path_of_wechat.get_wechat_path()
        if path:
            self.install_path_var.set(path.replace('\\', '/'))
        else:
            self.install_path_var.set("获取失败，请登录微信后获取或手动选择路径")

    def choose_install_path(self):
        while True:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
            if not path:  # 用户取消选择
                return
            path = path.replace('\\', '/')
            if path.lower().endswith('wechat.exe'):
                self.install_path_var.set(path)
                get_path_of_wechat.save_wechat_path_to_ini(path)
                break
            else:
                messagebox.showerror("错误", "请选择WeChat.exe文件")

    def get_data_path(self):
        path = get_path_of_data.get_wechat_data_path()
        if path:
            self.data_path_var.set(path.replace('\\', '/'))
        else:
            self.data_path_var.set("获取失败，请手动选择包含All Users文件夹的父文件夹（通常为Wechat Files）")

    def choose_data_path(self):
        while True:
            path = filedialog.askdirectory()
            if not path:  # 用户取消选择
                return
            path = path.replace('\\', '/')
            if get_path_of_data.is_valid_wechat_data_path(path):
                self.data_path_var.set(path)
                get_path_of_data.save_wechat_data_path_to_ini(path)
                break
            else:
                messagebox.showerror("错误", "该路径不是有效的存储路径，可以在微信设置中查看存储路径")


if __name__ == "__main__":
    root = tk.Tk()
    app = PathSettingWindow(root)
    root.mainloop()
