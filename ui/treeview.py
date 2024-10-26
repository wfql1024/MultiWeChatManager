import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# 初始化主窗口
root = tk.Tk()
root.title("Treeview 复选和图片显示")

# 创建 Treeview 控件
columns = ("数字", "英语", "中文", "中文大写")
tree = ttk.Treeview(root, columns=columns, show="tree headings", selectmode="none", takefocus=False)
tree.pack(padx=10, pady=10, fill="both", expand=True)

# 设置列标题，隐藏“英语”列
tree.heading("#0", text="图片")  # #0 列用于显示图片
for col in columns:
    tree.heading(col, text=col)  # 隐藏“英语”列的显示标题

tree.column("#0", stretch=tk.NO, minwidth=50, width=50, anchor="e")

# 隐藏“英语”这一整列
tree.column("英语", width=20, stretch=tk.NO)  # 将“英语”列的宽度设置为0

# 调整行高
style = ttk.Style()
style.configure("Treeview", rowheight=50)  # 设置行高为50

# 加载并调整图片
img_path = r"E:\Now\Desktop\微信图片_20241026034013.jpg"  # 替换为图片路径
img = Image.open(img_path)
img = img.resize((48, 48), Image.Resampling.NEAREST)  # 将图片调整为 40x40 大小以适应行高
photo = ImageTk.PhotoImage(img)

# 设置不可选行的灰色背景
tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
# 设置选中行的蓝色背景
tree.tag_configure("selected", background="lightblue", foreground="black")

# 插入50行数据，每行添加图片
data = [
    (str(i), f"Word {i}", f"字符{i}", f"字符大写{i}") for i in range(1, 51)
]
for row in data:
    item_id = row[0]
    tree.insert("", "end", iid=item_id, text="123", image=photo, values=row)
    # 偶数行禁用选中并置灰
    if int(item_id) % 2 == 0:
        current_tags = tree.item(item_id, "tags")
        if isinstance(current_tags, str) and current_tags == "":
            current_tags = ()  # 将空字符串转换为元组
        new_tags = current_tags + ("disabled",)  # 添加“disabled”
        tree.item(item_id, tags=new_tags)

# 存储图片引用，避免被回收
tree.image = photo

# 记录选中行的集合
selected_items = []


# 定义实时更新选中行列表显示的函数
def update_selected_display():
    # 获取选中行的“英语”列数据
    selected_english = [tree.item(item, "values")[1] for item in selected_items]
    selected_text_var.set("选中英语列: " + ", ".join(selected_english))
    # 检测是否仅选中一行来设置“单个”按钮状态
    btn_single.config(state="normal" if len(selected_items) == 1 else "disabled")
    print(selected_items)


# 定义点击事件，管理选中状态
def toggle_selection(event):
    item_id = tree.identify_row(event.y)
    if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            # 弹出提示窗口
            tk.messagebox.showinfo("提示", "你点击了图片")
        else:
            if item_id in selected_items:
                selected_items.remove(item_id)
                print(tree.item(item_id, "tags"))
                # 移除“selected”标签
                current_tags = tree.item(item_id, "tags")
                if isinstance(current_tags, str) and current_tags == "":
                    current_tags = ()  # 将空字符串转换为元组
                current_tags = tuple(tag for tag in current_tags if tag != "selected")  # 移除“selected”
                tree.item(item_id, tags=current_tags)
                print("↓")
                print(tree.item(item_id, "tags"))
            else:
                selected_items.append(item_id)
                # 添加“selected”标签
                current_tags = tree.item(item_id, "tags")
                if isinstance(current_tags, str) and current_tags == "":
                    current_tags = ()  # 将空字符串转换为元组
                new_tags = current_tags + ("selected",)  # 添加“selected”
                tree.item(item_id, tags=new_tags)
            update_selected_display()  # 实时更新选中行显示


# 绑定点击事件
tree.bind("<Button-1>", toggle_selection)


# 定义全选/取消选择按钮的功能
def toggle_select_all():
    if len(selected_items) < len([item for item in tree.get_children() if "disabled" not in tree.item(item, "tags")]):
        # 执行全选
        for item_id in tree.get_children():
            print(tree.item(item_id, "tags"))
            if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                selected_items.append(item_id)
                # 添加“selected”标签
                current_tags = tree.item(item_id, "tags")
                if isinstance(current_tags, str) and current_tags == "":
                    current_tags = ()  # 将空字符串转换为元组
                new_tags = current_tags + ("selected",)  # 添加“selected”
                tree.item(item_id, tags=new_tags)
    else:
        # 取消所有选择
        selected_items.clear()
        for item_id in tree.get_children():
            if "disabled" not in tree.item(item_id, "tags"):
                # 移除“selected”标签
                current_tags = tree.item(item_id, "tags")
                if isinstance(current_tags, str) and current_tags == "":
                    current_tags = ()  # 将空字符串转换为元组
                current_tags = tuple(tag for tag in current_tags if tag != "selected")  # 移除“selected”
                tree.item(item_id, tags=current_tags)
    update_selected_display()  # 更新显示


# 创建一个标签来实时显示选中行的“英语”列数据
selected_text_var = tk.StringVar()
selected_label = tk.Label(root, textvariable=selected_text_var, anchor="w")
selected_label.pack(fill="x", padx=10, pady=5)
selected_text_var.set("选中英语列: ")

# 创建按钮
btn_single = tk.Button(root, text="单个", state="disabled", command=lambda: tree.column("英语", width=0, stretch=tk.NO))
btn_single.pack(side="left", padx=10, pady=5)
btn_select_all = tk.Button(root, text="全选/取消全选", command=toggle_select_all)
btn_select_all.pack(side="right", padx=10, pady=5)

root.mainloop()
