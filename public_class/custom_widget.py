import tkinter as tk
from tkinter import ttk

from public_class.enums import NotebookDirection
from utils.encoding_utils import ColorUtils


class CustomLabelBtn(tk.Label):
    def __init__(self, parent, text, selected_bg='#00FF00', *args, **kwargs):
        super().__init__(parent, text=text, bg='white', relief='flat', padx=2, pady=2, *args, **kwargs)
        self.selected_bg = selected_bg
        self.hover_bg = ColorUtils.lighten_color(selected_bg, 0.8)
        self.click_command = None
        
        # 绑定悬浮和点击事件
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_button_down)
        self.bind('<ButtonRelease-1>', self._on_button_up)
        
    def set_selected(self, selected=True):
        """设置标签的选中状态"""
        self.configure(bg=self.selected_bg if selected else 'white')
        
    def _on_enter(self, event=None):
        """设置标签的悬浮状态"""
        if not self.cget('bg') == self.selected_bg:  # 未选中时才显示悬浮效果
            self.configure(bg=self.hover_bg)
            
    def _on_leave(self, event=None):
        """设置标签的悬浮状态"""
        if not self.cget('bg') == self.selected_bg:  # 未选中时才显示悬浮效果
            self.configure(bg='white')
            
    def on_click(self, command):
        """设置点击事件的回调函数"""
        self.click_command = command
        
    def _on_button_down(self, event=None):
        """按下按钮时的效果"""
        self.configure(bg=self.selected_bg)
        
    def _on_button_up(self, event=None):
        """松开按钮时的效果"""
        self.configure(bg=self.hover_bg)
        if self.click_command:
            self.click_command()
            
    def set_colors(self, selected_bg):
        """更新标签的颜色方案"""
        self.selected_bg = selected_bg
        self.hover_bg = ColorUtils.lighten_color(selected_bg, 0.8)
        # 保持当前状态
        if self.cget('bg') == self.selected_bg:
            self.configure(bg=selected_bg)


class CustomNotebook(ttk.Frame):
    def __init__(self, parent, direction=NotebookDirection.TOP, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.direction = direction
        self.tabs = {}
        self.current_tab = None
        self.selected_bg = '#00FF00'  # 默认选中颜色

        # 创建标签页和内容容器
        self._create_containers()

    def _create_containers(self):
        """创建标签页和内容容器"""
        # 根据方向创建容器
        if self.direction in [NotebookDirection.TOP, NotebookDirection.BOTTOM]:
            # 水平布局
            self.tab_frame = ttk.Frame(self)
            self.content_frame = ttk.Frame(self)

            # 根据方向设置pack顺序
            if self.direction == NotebookDirection.TOP:
                self.tab_frame.pack(side=tk.TOP, fill=tk.X)
                self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            else:
                self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                self.tab_frame.pack(side=tk.TOP, fill=tk.X)

        else:
            # 垂直布局
            self.tab_frame = ttk.Frame(self)
            self.content_frame = ttk.Frame(self)

            # 根据方向设置pack顺序
            if self.direction == NotebookDirection.LEFT:
                self.tab_frame.pack(side=tk.LEFT, fill=tk.Y)
                self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            else:
                self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                self.tab_frame.pack(side=tk.LEFT, fill=tk.Y)

    def set_colors(self, selected_bg='#00FF00'):
        """
        设置标签页的颜色
        :param selected_bg: 选中状态的背景色
        """
        self.selected_bg = selected_bg
        # 更新所有标签的颜色
        for tab_info in self.tabs.values():
            label = tab_info['label']
            label.set_colors(selected_bg)

    def add(self, text, frame):
        """
        添加新的标签页
        :param text: 标签页文本
        :param frame: 标签页内容框架
        """
        # 创建标签页
        tab = ttk.Frame(self.tab_frame)
        if self.direction in [NotebookDirection.TOP, NotebookDirection.BOTTOM]:
            tab.pack(side=tk.LEFT)
        else:
            tab.pack(side=tk.TOP, fill=tk.X)

        # 创建标签文本，若在侧边则竖向显示
        side_directions = [NotebookDirection.LEFT, NotebookDirection.RIGHT]
        display_text = '\n'.join(text) if self.direction in side_directions else text

        label = CustomLabelBtn(tab, text=display_text, selected_bg=self.selected_bg)
        label.pack(fill=tk.BOTH, expand=True)
        
        # 设置点击事件
        label.on_click(lambda t=text: self.select(t))

        # 存储标签页信息
        self.tabs[text] = {
            'frame': frame,
            'tab': tab,
            'label': label
        }

        # 如果是第一个标签页，自动选中
        if not self.current_tab:
            self.select(text)

    def select(self, text):
        """
        选择指定的标签页
        :param text: 标签页文本
        """
        # 取消当前标签页的选中状态
        if self.current_tab:
            self.tabs[self.current_tab]['label'].set_selected(False)

        # 设置新标签页的选中状态
        self.tabs[text]['label'].set_selected(True)
        self.current_tab = text

        # 显示对应的内容
        for tab_text, tab_info in self.tabs.items():
            if tab_text == text:
                tab_info['frame'].pack(fill=tk.BOTH, expand=True)
            else:
                tab_info['frame'].pack_forget()

if __name__ == '__main__':
    root = tk.Tk()
    root.geometry("400x300")

    # 创建竖向Notebook（左侧）
    notebook_left = CustomNotebook(root, direction=NotebookDirection.TOP)
    notebook_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # 创建横向Notebook（顶部）
    notebook_top = CustomNotebook(root, direction=NotebookDirection.TOP)
    notebook_top.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # 设置颜色（使用正绿色）
    notebook_left.set_colors(selected_bg='#00FF00')

    # 创建标签页
    frame1 = ttk.Frame(notebook_left)
    frame2 = ttk.Frame(notebook_left)
    frame3 = ttk.Frame(notebook_left)

    # 在标签页1中添加CustomLabelBtn
    btn1 = CustomLabelBtn(frame1, text="标签按钮1")
    btn1.on_click(lambda: print("按钮1被点击"))
    btn1.pack(pady=10)
    btn2 = CustomLabelBtn(frame1, text="标签按钮2")
    btn2.on_click(lambda: print("按钮2被点击"))
    btn2.pack(pady=10)

    # 在标签页2中添加CustomLabelBtn和标签
    ttk.Label(frame2, text="这是标签页2").pack(pady=10)
    btn3 = CustomLabelBtn(frame2, text="标签按钮3")
    btn3.on_click(lambda: print("按钮3被点击"))
    btn3.pack(pady=10)

    # 在标签页3中添加CustomLabelBtn组
    btn_frame = ttk.Frame(frame3)
    btn_frame.pack(pady=20)
    btn4 = CustomLabelBtn(btn_frame, text="标签按钮4")
    btn4.on_click(lambda: print("按钮4被点击"))
    btn4.pack(side=tk.LEFT, padx=5)
    btn5 = CustomLabelBtn(btn_frame, text="标签按钮5")
    btn5.on_click(lambda: print("按钮5被点击"))
    btn5.pack(side=tk.LEFT, padx=5)

    # 添加标签页
    notebook_left.add("标签1", frame1)
    notebook_left.add("标签2", frame2)
    notebook_left.add("标签3", frame3)

    root.mainloop()