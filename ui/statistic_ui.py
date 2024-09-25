import tkinter as tk
from tkinter import ttk
from resources import Config
from utils import json_utils, handle_utils


def try_convert(value):
    try:
        return float(value)
    except ValueError:
        return value


class StatisticWindow:
    def __init__(self, master):
        self.manual_tree = None
        self.auto_tree = None
        self.index_combobox = None
        self.master = master
        self.master.title("统计数据")
        self.master.attributes('-toolwindow', True)
        self.window_width = 420
        self.window_height = 540
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = (screen_height - self.window_height) // 2
        master.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        master.update_idletasks()

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        self.scrollbar_frame = tk.Frame(master)
        self.scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(master, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(self.scrollbar_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        # 创建一个Frame在Canvas中
        self.main_frame = ttk.Frame(self.canvas)
        # 将main_frame放置到Canvas的窗口中，并禁用Canvas的宽高跟随调整
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        # 将滚动条连接到Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        # 配置Canvas的滚动区域
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        self.sort_order = {"manual": True, "auto": True}  # 控制排序顺序

        self.create_manual_table()
        self.create_auto_table()

        self.display_table()

    def on_mousewheel(self, event):
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

    def bind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", self.on_mousewheel, add='+')
        widget.bind("<Button-4>", self.on_mousewheel, add='+')
        widget.bind("<Button-5>", self.on_mousewheel, add='+')

        for child in widget.winfo_children():
            self.bind_mouse_wheel(child)

    def unbind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.unbind("<MouseWheel>")
        widget.unbind("<Button-4>")
        widget.unbind("<Button-5>")

        for child in widget.winfo_children():
            self.unbind_mouse_wheel(child)

    def on_canvas_configure(self, event):
        """动态调整canvas中窗口的宽度，并根据父子间高度关系进行滚轮事件绑定与解绑"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        width = event.width
        self.canvas.itemconfig(self.canvas_window, width=width)

        if self.main_frame.winfo_height() > self.canvas.winfo_height():
            self.bind_mouse_wheel(self.canvas)
            self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        else:
            self.unbind_mouse_wheel(self.canvas)
            self.scrollbar.pack_forget()

    def create_manual_table(self):
        label = tk.Label(self.main_frame, text="手动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack(padx=(20, 0))

        self.manual_tree = ttk.Treeview(self.main_frame, columns=("模式", "最短时间", "使用次数", "平均时间", "最长时间"),
                                        show='headings', height=1)
        for col in ("模式", "最短时间", "使用次数", "平均时间", "最长时间"):
            self.manual_tree.heading(col, text=col,
                                     command=lambda c=col: self.sort_column(self.manual_tree, c, "manual"))
            self.manual_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.manual_tree.pack(fill=tk.X, expand=True, padx=(20, 0), pady=(0, 10))

    def create_auto_table(self):
        label = tk.Label(self.main_frame, text="自动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack(padx=(20, 10))

        description = tk.Label(self.main_frame, text="查看登录第i个账号的数据：")
        description.pack()

        self.index_combobox = ttk.Combobox(self.main_frame, values=[], state="readonly")
        self.index_combobox.pack()
        self.index_combobox.bind("<<ComboboxSelected>>", self.update_auto_table)

        self.auto_tree = ttk.Treeview(self.main_frame, columns=("模式", "最短时间", "使用次数", "平均时间", "最长时间"),
                                      show='headings', height=1)
        for col in ("模式", "最短时间", "使用次数", "平均时间", "最长时间"):
            self.auto_tree.heading(col, text=col, command=lambda c=col: self.sort_column(self.auto_tree, c, "auto"))
            self.auto_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.auto_tree.pack(fill=tk.X, expand=True, padx=(20, 0), pady=(0, 10))

    def display_table(self):
        data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)

        # 清空之前的数据
        for item in self.manual_tree.get_children():
            self.manual_tree.delete(item)
        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)

        # 添加手动统计数据
        manual_data = data.get("manual", {}).items()
        for mode, stats in manual_data:
            min_time, count, avg_time, max_time = stats.split(",")
            self.manual_tree.insert("", "end",
                                    values=(mode, min_time.replace("inf", "null"),
                                            int(float(count)), avg_time, max_time))
        self.manual_tree.config(height=len(manual_data) + 1)

        # 更新下拉框选项
        auto_data = data.get("auto", {})
        index_values = []
        for mode, times_dict in auto_data.items():
            index_values.extend(times_dict.keys())  # 获取所有index值
        self.index_combobox['values'] = index_values

        if self.index_combobox['values']:  # 确保下拉框有值
            self.index_combobox.current(0)  # 默认选择第一个
            self.update_auto_table_selection(self.index_combobox.get())

        self.adjust_column_width(self.manual_tree)
        self.adjust_column_width(self.auto_tree)

    def adjust_column_width(self, tree):
        for col in tree["columns"]:
            tree.column(col, width=int(self.window_width // len(tree["columns"]) - 10))  # 计算并设置适合的列宽

    def update_auto_table_selection(self, selected_index):
        data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)

        # 清空之前的数据
        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)

        auto_data = data.get("auto", {}).items()
        for mode, times_dict in auto_data:
            if selected_index in times_dict:  # 仅显示选中的index
                stats = times_dict[selected_index]
                min_time, count, avg_time, max_time = stats.split(",")
                self.auto_tree.insert("", "end",
                                      values=(mode, min_time.replace("inf", "null"),
                                              int(float(count)), avg_time, max_time))
        self.auto_tree.config(height=len(auto_data) + 1)

    def update_auto_table(self, event):
        selected_index = self.index_combobox.get()  # 获取选中的index
        self.update_auto_table_selection(selected_index)

    def sort_column(self, tree, col, table_type):
        items = [(tree.item(i)["values"], i) for i in tree.get_children()]
        is_ascending = self.sort_order[table_type]

        items.sort(key=lambda x: (try_convert(x[0][list(tree["columns"]).index(col)])
                                  if col not in ["模式"] else x[0][list(tree["columns"]).index(col)]),
                   reverse=not is_ascending)

        # 清空表格并重新插入排序后的数据
        for i in tree.get_children():
            tree.delete(i)
        for item in items:
            tree.insert("", "end", values=item[0])

        tree.configure(height=len(items) + 1)

        self.sort_order[table_type] = not is_ascending  # 切换排序顺序


# 创建主窗口
if __name__ == "__main__":
    root = tk.Tk()
    statistic_window = StatisticWindow(root)
    root.mainloop()
