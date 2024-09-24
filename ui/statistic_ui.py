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
        self.window_width = None
        self.master = master
        self.master.title("统计数据")
        master.attributes('-toolwindow', True)
        window_width = 420
        window_height = 540
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        master.geometry(f"{window_width}x{window_height}+{x}+{y}")
        master.update_idletasks()
        self.window_width = window_width

        self.sort_order = {"manual": True, "auto": True}  # 控制排序顺序

        self.create_manual_table()
        self.create_auto_table()

        self.display_table()

    def create_manual_table(self):
        label = tk.Label(self.master, text="手动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack()

        self.manual_tree = ttk.Treeview(self.master, columns=("模式", "最短时间", "使用次数", "平均时间", "最长时间"),
                                        show='headings')
        for col in ("模式", "最短时间", "使用次数", "平均时间", "最长时间"):
            self.manual_tree.heading(col, text=col,
                                     command=lambda c=col: self.sort_column(self.manual_tree, c, "manual"))
            self.manual_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.manual_tree.pack(fill=tk.BOTH, expand=True)

    def create_auto_table(self):
        label = tk.Label(self.master, text="自动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack()

        description = tk.Label(self.master, text="查看登录第i个账号的数据：")
        description.pack()

        self.index_combobox = ttk.Combobox(self.master, values=[], state="readonly")
        self.index_combobox.pack()
        self.index_combobox.bind("<<ComboboxSelected>>", self.update_auto_table)

        self.auto_tree = ttk.Treeview(self.master, columns=("模式", "最短时间", "使用次数", "平均时间", "最长时间"),
                                      show='headings')
        for col in ("模式", "最短时间", "使用次数", "平均时间", "最长时间"):
            self.auto_tree.heading(col, text=col, command=lambda c=col: self.sort_column(self.auto_tree, c, "auto"))
            self.auto_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.auto_tree.pack(fill=tk.BOTH, expand=True)

    def display_table(self):
        account_data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)

        # 清空之前的数据
        for item in self.manual_tree.get_children():
            self.manual_tree.delete(item)
        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)

        # 添加手动统计数据
        for mode, stats in account_data.get("manual", {}).items():
            min_time, count, avg_time, max_time = stats.split(",")
            self.manual_tree.insert("", "end",
                                    values=(mode, min_time.replace("inf", "null"),
                                            int(float(count)), avg_time, max_time))

        # 更新下拉框选项
        auto_data = account_data.get("auto", {})
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
            tree.column(col, width=int(self.window_width // len(tree["columns"])))  # 计算并设置适合的列宽

    def update_auto_table_selection(self, selected_index):
        account_data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)

        # 清空之前的数据
        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)

        for mode, times_dict in account_data.get("auto", {}).items():
            if selected_index in times_dict:  # 仅显示选中的index
                stats = times_dict[selected_index]
                min_time, count, avg_time, max_time = stats.split(",")
                self.auto_tree.insert("", "end",
                                      values=(mode, min_time.replace("inf", "null"),
                                              int(float(count)), avg_time, max_time))

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

        self.sort_order[table_type] = not is_ascending  # 切换排序顺序


# 创建主窗口
if __name__ == "__main__":
    root = tk.Tk()
    statistic_window = StatisticWindow(root)
    root.mainloop()
