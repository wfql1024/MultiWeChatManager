import tkinter as tk


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() - 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def disable_button_and_add_tip(tooltips, button, text):
    """
    禁用按钮，启用提示
    :return: None
    """
    button.state(['disabled'])
    if button not in tooltips:
        tooltips[button] = Tooltip(button, text)


def enable_button_and_unbind_tip(tooltips, button):
    """
    启用按钮，去除提示
    :return: None
    """
    button.state(['!disabled'])
    if button in tooltips:
        tooltips[button].widget.unbind("<Enter>")
        tooltips[button].widget.unbind("<Leave>")
        del tooltips[button]


def remove_a_tag_of_item(tree, item_id, tag_to_remove):
    # 移除“selected”标签
    current_tags = tree.item(item_id, "tags")
    if isinstance(current_tags, str) and current_tags == "":
        current_tags = ()  # 将空字符串转换为元组
    new_tags = tuple(tag for tag in current_tags if tag != tag_to_remove)
    tree.item(item_id, tags=list(new_tags))
    print(current_tags, new_tags, tree.item(item_id, "tags"))


def add_a_tag_to_item(tree, item_id, tag_to_add):
    # 添加“selected”标签
    current_tags = tree.item(item_id, "tags")
    if isinstance(current_tags, str) and current_tags == "":
        current_tags = ()  # 将空字符串转换为元组
    new_tags = current_tags + (tag_to_add,)
    tree.item(item_id, tags=list(new_tags))
    print(current_tags, new_tags, tree.item(item_id, "tags"))
