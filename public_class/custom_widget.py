import tkinter as tk
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from tkinter import ttk

from public_class.enums import NotebookDirection
from utils import widget_utils
from utils.encoding_utils import ColorUtils


class CustomWidget(ABC):
    class State(str, Enum):
        NORMAL = "normal"
        DISABLED = "disabled"
        SELECTED = "selected"
        CLICKED = "clicked"
        HOVERED = "hovered"

    @abstractmethod
    def set_state(self, state: State):
        """
        设置控件的状态。子类必须重写此方法。
        :param state: CustomWidget.State 枚举值
        """
        pass

    @staticmethod
    def set_all_custom_widgets_to_(frame, state: State):
        """
        将指定框架内所有继承自 CustomWidget 的控件设置为指定状态（递归子控件）

        :param frame: 要处理的 Frame 或控件容器
        :param state: CustomWidget.State 中的状态值
        """
        for child in frame.winfo_children():
            if isinstance(child, CustomWidget):
                child.set_state(state)
            # 如果子控件也是容器（比如 Frame），递归处理
            if isinstance(child, (tk.Frame, ttk.Frame)):
                CustomWidget.set_all_custom_widgets_to_(child, state)


class CustomLabelBtn(tk.Label, CustomWidget, ABC):
    def __init__(self, parent, text, *args, **kwargs):
        super().__init__(parent, text=text, relief='flat', *args, **kwargs)
        self.styles = {}
        self._shake_running = None
        self.state = self.State.NORMAL

        self.down = False
        # 加载默认样式
        default_major_bg_color = '#B2E0F7'  # 主后色: 淡蓝色
        default_major_fg_color = 'black'  # 主前色: 黑色

        default_normal_bg = 'white'  # 正常背景色: 白色
        default_normal_fg = default_major_fg_color  # 正常前景色: 黑色
        default_selected_bg = default_major_bg_color
        default_selected_fg = default_major_fg_color
        default_clicked_bg = default_major_bg_color
        default_clicked_fg = default_major_fg_color
        default_hovered_bg = ColorUtils.lighten_color(default_selected_bg, 0.8)
        default_hovered_fg = default_selected_fg
        default_disabled_bg = '#F5F7FA'  # 禁用背景色: 浅灰色
        default_disabled_fg = 'grey'  # 禁用前景色: 灰色

        default_styles = {
            self.State.DISABLED: {'bg': default_disabled_bg, 'fg': default_disabled_fg},
            self.State.SELECTED: {'bg': default_selected_bg, 'fg': default_selected_fg},
            self.State.CLICKED: {'bg': default_clicked_bg, 'fg': default_clicked_fg},
            self.State.HOVERED: {'bg': default_hovered_bg, 'fg': default_hovered_fg},
            self.State.NORMAL: {'bg': default_normal_bg, 'fg': default_normal_fg}
        }
        self.set_styles(default_styles)

        # self.click_command = None

        self.bind('<Enter>', self._on_enter, add='+')
        self.bind('<Leave>', self._on_leave, add='+')
        self.bind('<Button-1>', self._on_button_down, add='+')
        self.bind('<ButtonRelease-1>', self._on_button_up, add='+')

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

    def _update_style(self):
        """根据当前状态更新样式"""
        self.configure(**self.styles[self.state])

    def _on_enter(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED or self.state == self.State.SELECTED:
            return
        if self.down:
            self.set_state(self.State.CLICKED)
        else:
            self.set_state(self.State.HOVERED)

    def _on_leave(self, event=None):
        if event:
            pass
        if self.state == self.State.DISABLED or self.state == self.State.SELECTED:
            return
        self.set_state(self.State.NORMAL)

    def _on_button_down(self, event=None):
        self.down = True
        print("按下")
        if event:
            pass
        if self.state == self.State.DISABLED:
            self._shake()
            return
        if self.state == self.State.SELECTED:
            return
        # 按下是短暂的选中状态
        self.set_state(self.State.CLICKED)

    def _on_button_up(self, event=None):
        self.down = False
        print("抬起")
        if event:
            pass
        if self.state == self.State.DISABLED or self.state == self.State.SELECTED:
            return
        # 按下鼠标后，当抬起时位置不在按钮处，应该取消点击的状态
        x, y = self.winfo_pointerxy()
        widget = self.winfo_containing(x, y)
        if widget is not self:
            self.set_state(self.State.NORMAL)
            return
        self.set_state(self.State.HOVERED)

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


class CustomNotebook:
    def __init__(self, root, parent_frame, direction=NotebookDirection.TOP, *args, **kwargs):
        self.direction = direction
        self.root = root
        self.tabs = {}
        self.curr_tab_id = None
        self.selected_bg = '#00FF00'  # 默认选中颜色
        self.select_callback = None  # 选中回调函数

        self.notebook_frame = ttk.Frame(parent_frame, *args, **kwargs)
        self._pack_frame()
        self._create_containers()

    def _pack_frame(self):
        direction = self.direction
        if direction == NotebookDirection.TOP:
            self.notebook_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        elif direction == NotebookDirection.BOTTOM:
            self.notebook_frame.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        elif direction == NotebookDirection.LEFT:
            self.notebook_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        elif direction == NotebookDirection.RIGHT:
            self.notebook_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

    def _create_containers(self):
        """创建标签页和内容容器"""
        # 根据方向创建容器
        if self.direction in [NotebookDirection.TOP, NotebookDirection.BOTTOM]:
            # 水平布局
            self.tabs_frame = ttk.Frame(self.notebook_frame)
            self.frames_pool = ttk.Frame(self.notebook_frame)

            # 根据方向设置pack顺序
            if self.direction == NotebookDirection.TOP:
                self.tabs_frame.pack(side=tk.TOP, fill=tk.X)
                self.frames_pool.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            else:
                self.frames_pool.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                self.tabs_frame.pack(side=tk.TOP, fill=tk.X)

        else:
            # 垂直布局
            self.tabs_frame = ttk.Frame(self.notebook_frame)
            self.frames_pool = ttk.Frame(self.notebook_frame)

            # 根据方向设置pack顺序
            if self.direction == NotebookDirection.LEFT:
                self.tabs_frame.pack(side=tk.LEFT, fill=tk.Y)
                self.frames_pool.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            else:
                self.frames_pool.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                self.tabs_frame.pack(side=tk.LEFT, fill=tk.Y)

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

    def add(self, tab_id, text, frame):
        """
        添加新的标签页
        :param tab_id: 标签页标识
        :param text: 标签页文本
        :param frame: 标签页内容框架
        """
        # 创建标签页
        print(f"添加标签页：{tab_id}")
        tab_frame = ttk.Frame(self.tabs_frame)
        if self.direction in [NotebookDirection.TOP, NotebookDirection.BOTTOM]:
            tab_frame.pack(side=tk.LEFT)
        else:
            tab_frame.pack(side=tk.TOP, fill=tk.X)

        # 创建标签文本，若在侧边则竖向显示
        side_directions = [NotebookDirection.LEFT, NotebookDirection.RIGHT]
        display_text = '\n'.join(text) if self.direction in side_directions else text

        tab_label = CustomLabelBtn(tab_frame, text=display_text)
        tab_label.pack(fill=tk.BOTH, expand=True)

        # 设置点击事件
        # tab_label.on_click(lambda i=tab_id: self.select(i))
        widget_utils.UnlimitedClickHandler(
            self.root,
            tab_label,
            **{"1": partial(self.select, tab_id),
               "2": partial(self.select, tab_id)}

        )

        # 存储标签页信息
        self.tabs[tab_id] = {
            'text': text,
            'tab': tab_label,
            'frame': frame,
            'tab_frame': tab_frame,
        }

        # # 如果是第一个标签页，自动选中
        # if not self.curr_tab_id:
        #     self.select(tab_id)

    def select(self, tab_id):
        """
        选择指定的标签页
        :param tab_id: 标签页文本
        """
        # 取消当前标签页的选中状态
        if self.curr_tab_id:
            # print(f"取消标签：{self.current_tab}")
            self.tabs[self.curr_tab_id]['tab'].set_state(CustomLabelBtn.State.NORMAL)

        # 设置新标签页的选中状态
        # print(f"选中标签：{text}")
        self.tabs[tab_id]['tab'].set_state(CustomLabelBtn.State.SELECTED)
        self.curr_tab_id = tab_id

        # 显示对应的内容
        for tab_text, tab_info in self.tabs.items():
            if tab_text == tab_id:
                tab_info['frame'].pack(fill=tk.BOTH, expand=True)
            else:
                tab_info['frame'].pack_forget()

        if callable(self.select_callback):
            self.select_callback()


if __name__ == '__main__':
    root = tk.Tk()
    root.geometry("400x300")


    def printer(click_time):
        print("按钮功能:连点次数为", click_time)


    # 创建竖向Notebook（左侧）
    # left_nb_cls = CustomNotebook(root, direction=NotebookDirection.LEFT)

    # 创建横向Notebook（顶部）
    top_nb_cls = CustomNotebook(root, root, direction=NotebookDirection.TOP)

    my_nb_cls = top_nb_cls
    # 设置颜色（使用正绿色）
    my_nb_cls.set_major_color(selected_bg='#00FF00')

    nb_content_frame = top_nb_cls.frames_pool

    # 创建标签页
    frame1 = ttk.Frame(nb_content_frame)
    frame2 = ttk.Frame(nb_content_frame)
    frame3 = ttk.Frame(nb_content_frame)

    # 在标签页1中添加CustomLabelBtn
    btn1 = CustomLabelBtn(frame1, text="标签按钮1")
    # btn1.on_click(lambda: print("按钮1被点击"))
    btn1.pack(pady=10)
    widget_utils.UnlimitedClickHandler(
        root, btn1,
        printer

    )
    btn2 = CustomLabelBtn(frame1, text="标签按钮2")
    # btn2.on_click(lambda: print("按钮2被点击"))
    btn2.pack(pady=10)

    # 在标签页2中添加CustomLabelBtn和标签
    ttk.Label(frame2, text="这是标签页2").pack(pady=10)
    btn3 = CustomLabelBtn(frame2, text="标签按钮3")
    # btn3.on_click(lambda: print("按钮3被点击"))
    btn3.pack(pady=10)

    # 在标签页3中添加CustomLabelBtn组
    btn_frame = ttk.Frame(frame3)
    btn_frame.pack(pady=20)
    btn4 = CustomLabelBtn(btn_frame, text="标签按钮4")
    # btn4.on_click(lambda: print("按钮4被点击"))
    btn4.pack(side=tk.LEFT, padx=5)
    btn5 = CustomLabelBtn(btn_frame, text="标签按钮5")
    # btn5.on_click(lambda: print("按钮5被点击"))
    btn5.pack(side=tk.LEFT, padx=5)

    # 添加标签页
    my_nb_cls.add("tab1", "标签1", frame1)
    my_nb_cls.add("tab2", "标签2", frame2)
    my_nb_cls.add("tab3", "标签3", frame3)

    root.mainloop()
