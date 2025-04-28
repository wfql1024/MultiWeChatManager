import tkinter as tk
from abc import ABC, abstractmethod
from enum import Enum
from tkinter import ttk

from public_class.enums import NotebookDirection
from utils.encoding_utils import ColorUtils


class CustomWidget(ABC):
    class State(str, Enum):
        NORMAL = "normal"
        DISABLED = "disabled"
        SELECTED = "selected"
        HOVERED = "hovered"

    @abstractmethod
    def set_state(self, state: State):
        """
        设置控件的状态。子类必须重写此方法。
        :param state: CustomWidget.State 枚举值
        """
        pass


class CustomLabelBtn(tk.Label, CustomWidget, ABC):
    def __init__(self, parent, text, *args, **kwargs):
        super().__init__(parent, text=text, relief='flat', *args, **kwargs)
        self.styles = {}
        self._shake_running = None
        self.state = self.State.NORMAL

        # 加载默认样式
        default_major_bg_color = '#B2E0F7'  # 主后色: 淡蓝色
        default_major_fg_color = 'black'  # 主前色: 黑色

        default_normal_bg = 'white'  # 正常背景色: 白色
        default_normal_fg = default_major_fg_color  # 正常前景色: 黑色
        default_selected_bg = default_major_bg_color
        default_selected_fg = default_major_fg_color
        default_hovered_bg = ColorUtils.lighten_color(default_selected_bg, 0.8)
        default_hovered_fg = default_selected_fg
        default_disabled_bg = '#F5F7FA'  # 禁用背景色: 浅灰色
        default_disabled_fg = 'grey'  # 禁用前景色: 灰色

        default_styles = {
            self.State.DISABLED: {'bg': default_disabled_bg, 'fg': default_disabled_fg},
            self.State.SELECTED: {'bg': default_selected_bg, 'fg': default_selected_fg},
            self.State.HOVERED: {'bg': default_hovered_bg, 'fg': default_hovered_fg},
            self.State.NORMAL: {'bg': default_normal_bg, 'fg': default_normal_fg}
        }
        self.set_styles(default_styles)

        self.click_command = None

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_button_down)
        self.bind('<ButtonRelease-1>', self._on_button_up)

        self._update_style()

    def set_state(self, state):
        """设置状态"""
        if not isinstance(state, self.State):
            raise ValueError("state必须是CustomLabelBtn.State的枚举值")
        self.state = state
        self._update_style()

    def set_major_colors(self, selected_bg):
        """设置主要颜色（选中背景色和悬浮背景色）"""
        hover_bg = ColorUtils.lighten_color(selected_bg, 0.8)

        self.styles[self.State.SELECTED]['bg'] = selected_bg
        self.styles[self.State.HOVERED]['bg'] = hover_bg

        self._update_style()

    def set_styles(self, styles):
        """
        批量更新样式配置

        参数:
            styles (dict): 传入一个字典，格式例如：
                {
                    'disabled': {'fg': 'red'},
                    'selected': {'bg': '#00FF00', 'fg': 'white'},
                }
        说明：
            - 字典的键是状态名（'disabled', 'selected', 'hovered', 'normal'）
            - 每个值是一个dict，里面是Tkinter支持的样式参数（如'bg', 'fg'等）
            - 只修改指定的部分，不影响其他已有配置
        """
        if not isinstance(styles, dict):
            raise ValueError("styles必须是字典")

        for key, value in styles.items():
            if key not in self.State._value2member_map_:
                print(f"[Warning] 未知的状态名: '{key}'，跳过。必须是 {list(self.State._value2member_map_.keys())}")
                continue
            if not isinstance(value, dict):
                print(f"[Warning] 状态 '{key}' 的样式必须是字典，但收到的是 {type(value).__name__}，跳过。")
                continue
            if key not in self.styles:
                self.styles[key] = {}
            self.styles[key].update(value)

        self._update_style()

    def on_click(self, command):
        """设置点击回调"""
        self.click_command = command

    def _update_style(self):
        """根据当前状态更新样式"""
        self.configure(**self.styles[self.state])

    def _on_enter(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED:
            return
        # 若已被长久选中，则保持选中状态
        if self.state != self.State.SELECTED:
            self.set_state(self.State.HOVERED)

    def _on_leave(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED:
            return
        # 若已被长久选中，则保持选中状态
        if self.state != self.State.SELECTED:
            self.set_state(self.State.NORMAL)

    def _on_button_down(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED:
            self._shake()
            return
        # 按下是短暂的选中状态
        self.set_state(self.State.SELECTED)

    def _on_button_up(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED:
            return

        # 按下鼠标后，当抬起时位置不在按钮处，应该取消点击的状态
        x, y = self.winfo_pointerxy()
        widget = self.winfo_containing(x, y)
        if widget is not self:
            self.set_state(self.State.NORMAL)
            return

        # 松开时若不是选中状态，则恢复为悬浮状态；若是长久选中状态，则保持
        if self.state != self.State.SELECTED:
            self.set_state(self.State.HOVERED)

        # 如果有命令，则恢复为常规状态，并执行
        if self.click_command:
            self.set_state(self.State.NORMAL)
            self.click_command()

    def _shake(self):
        """禁用状态下点击，抖动一下提示，不破坏布局"""
        if self._shake_running:
            return
        self._shake_running = True

        if self.winfo_manager() != 'pack':
            return

        info = self.pack_info()
        original_padx = info.get('padx', 0)
        dx = [2, -2, 2, -2, 0]

        def move(index=0):
            if index < len(dx):
                new_padx = max(0, original_padx + dx[index])
                self.pack_configure(padx=new_padx)
                self.after(30, move, index + 1)
            else:
                self.pack_configure(padx=original_padx)
                self._shake_running = False

        move()


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

    def set_major_color(self, selected_bg='#00FF00'):
        """
        设置标签页的颜色
        :param selected_bg: 选中状态的背景色
        """
        self.selected_bg = selected_bg
        # 更新所有标签的颜色
        for tab_info in self.tabs.values():
            label = tab_info['label']
            label.set_major_colors(selected_bg)

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

        label = CustomLabelBtn(tab, text=display_text)
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
            # print(f"取消标签：{self.current_tab}")
            self.tabs[self.current_tab]['label'].set_state(CustomLabelBtn.State.NORMAL)

        # 设置新标签页的选中状态
        # print(f"选中标签：{text}")
        self.tabs[text]['label'].set_state(CustomLabelBtn.State.SELECTED)
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
    notebook_left = CustomNotebook(root, direction=NotebookDirection.LEFT)
    notebook_left.pack(fill=tk.BOTH, expand=True)

    # 创建横向Notebook（顶部）
    notebook_top = CustomNotebook(root, direction=NotebookDirection.TOP)
    # notebook_top.pack(fill=tk.BOTH, expand=True)

    my_notebook = notebook_left

    # 设置颜色（使用正绿色）
    my_notebook.set_major_color(selected_bg='#00FF00')

    # 创建标签页
    frame1 = ttk.Frame(my_notebook)
    frame2 = ttk.Frame(my_notebook)
    frame3 = ttk.Frame(my_notebook)

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
    my_notebook.add("标签1", frame1)
    my_notebook.add("标签2", frame2)
    my_notebook.add("标签3", frame3)

    root.mainloop()
