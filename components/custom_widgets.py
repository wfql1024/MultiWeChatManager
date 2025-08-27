import tkinter as tk
from enum import Enum
from tkinter import ttk
from typing import Union

from public.custom_classes import Condition, Conditions
from utils.encoding_utils import ColorUtils
from utils.widget_utils import UnlimitedClickHandler, CanvasUtils, WidgetUtils


class DefaultEntry(tk.Entry):
    """会提前填入默认内容的文本框"""

    def __init__(self, master=None, default_label="请输入内容", **kwargs):
        self.var = tk.StringVar()
        super().__init__(master, textvariable=self.var, **kwargs)
        self.default_label = default_label
        self._is_default = False
        self._set_default()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _set_default(self):
        self.var.set(self.default_label)
        self._is_default = True
        self._set_style()

    def _set_style(self):
        self.config(fg=("grey" if self._is_default else "black"))

    def _on_focus_in(self, event):
        if event:
            pass
        if self._is_default:
            self.var.set("")
            self._is_default = False
            self._set_style()

    def _on_focus_out(self, event):
        if event:
            pass
        var = self.var.get()
        if not var or not self.var.get().strip():
            # 空值情况下恢复默认值
            self._set_default()
        else:
            # 否则就正常显示
            self._is_default = False
            self._set_style()

    def get_value(self):
        return None if self._is_default else self.var.get()

    def set_value(self, value):
        """外部设置值"""
        if value is not None:
            self.var.set(value)
            self._on_focus_out(None)


class CustomBtn(tk.Widget):
    _default_styles = {}
    _styles = {}
    _down = False
    _above = False
    _text = ""
    _click_map = {}
    _click_func = None
    _click_time = 0
    _shake_running = None
    _state = None
    _core_widget = None

    class State(str, Enum):
        NORMAL = "normal"
        DISABLED = "disabled"
        SELECTED = "selected"
        CLICKED = "clicked"
        HOVERED = "hovered"

    def _init_custom_btn_attrs(self):
        # print("加载CustomBtn类的属性...")
        self._default_styles = {}
        self._styles = {}
        self._down = False
        self._above = False
        self._text = ""
        self._click_map = {}
        self._click_func = None
        self._click_time = 0
        self._shake_running = None
        self._state = None
        self._core_widget = None
        # 默认颜色
        default_major_bg_color = '#B2E0F7'  # 主后色: 淡蓝色
        default_major_fg_color = 'black'  # 主前色: 黑色
        default_bg = {
            self.State.NORMAL: "white",
            self.State.HOVERED: ColorUtils.fade_color(default_major_bg_color),
            self.State.CLICKED: default_major_bg_color,
            self.State.DISABLED: "#F9F9F9",
            self.State.SELECTED: default_major_bg_color
        }
        default_fg = {
            self.State.NORMAL: default_major_fg_color,
            self.State.HOVERED: default_major_fg_color,
            self.State.CLICKED: default_major_fg_color,
            self.State.DISABLED: "grey",
            self.State.SELECTED: default_major_fg_color
        }
        default_bdc = {
            self.State.NORMAL: "#D0D0D0",
            self.State.HOVERED: default_major_bg_color,
            self.State.CLICKED: ColorUtils.brighten_color(default_major_bg_color),
            self.State.DISABLED: "#E9E9E9",
            self.State.SELECTED: ColorUtils.brighten_color(default_major_bg_color)
        }
        for key in [self.State.NORMAL, self.State.HOVERED, self.State.CLICKED, self.State.DISABLED,
                    self.State.SELECTED]:
            self._default_styles[key] = {'bg': default_bg[key], 'fg': default_fg[key], 'bdc': default_bdc[key]}

    def set_bind_map(self, **kwargs):
        """传入格式: **{"数字": 回调函数, ...},添加后需要apply_bind()才能生效"""
        for key, value in kwargs.items():
            self._click_map[key] = value
        return self

    def set_bind_func(self, func):
        """传入带有click_time参数的方法,变量名必须是click_time"""
        self._click_func = func
        return self

    def apply_bind(self, tkinter_root):
        """可以多次应用,每次应用不覆盖之前绑定的事件,注意不要重复,最好是在所有set_bind之后才apply_bind"""
        UnlimitedClickHandler(
            tkinter_root,
            self._core_widget,
            self._click_func,
            self,
            **self._click_map
        )
        # 绑定后清空map和func
        self._click_map = {}
        self._click_func = None

    def reset_bind(self):
        WidgetUtils.unbind_all_events(self._core_widget)
        self._bind_event()

    def _bind_event(self):
        self._core_widget.bind("<Enter>", self._on_enter)
        self._core_widget.bind("<Leave>", self._on_leave)
        self._core_widget.bind("<Button-1>", self._on_button_down)
        self._core_widget.bind("<ButtonRelease-1>", self._on_button_up)
        self._core_widget.bind("<Configure>", lambda e: self._draw())

    def redraw(self):
        """应用并重绘,前面可以链式修改"""
        self._draw()

    def get_state(self):
        """获取当前状态"""
        return self._state

    def set_state(self, state):
        """设置状态"""
        if state not in [self.State.DISABLED, self.State.SELECTED, self.State.NORMAL]:
            raise ValueError(
                "state必须是CustomLabelBtn.State的枚举值, 且推荐在DISABLED, SELECTED, NORMAL三种状态内使用")
        self._state = state
        self._draw()

    def set_major_colors(self, major_color):
        """设置主要颜色（选中背景色和悬浮背景色）, 格式必须是#开头的16进制颜色"""
        lighten_color = ColorUtils.fade_color(major_color)
        brighten_color = ColorUtils.brighten_color(major_color)
        self._styles[self.State.HOVERED]['bg'] = lighten_color
        self._styles[self.State.SELECTED]['bg'] = major_color
        self._styles[self.State.CLICKED]['bg'] = major_color
        self._styles[self.State.HOVERED]['bdc'] = major_color
        self._styles[self.State.CLICKED]['bdc'] = brighten_color
        self._styles[self.State.SELECTED]['bdc'] = brighten_color
        return self

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
            if key not in self._styles:
                self._styles[key] = {}
            self._styles[key].update(value)

        return self

    def _draw(self, tmp_state=None):
        ...

    @staticmethod
    def set_all_custom_widgets_to_(frame, state: State):
        """
        将指定框架内所有继承自 CustomWidget 的控件设置为指定状态（递归子控件）

        :param frame: 要处理的 Frame 或控件容器
        :param state: CustomWidget.State 中的状态值
        """
        for child in frame.winfo_children():
            if isinstance(child, CustomBtn):
                child.set_state(state)
            # 如果子控件也是容器（比如 Frame），递归处理
            if isinstance(child, (tk.Frame, ttk.Frame)):
                CustomBtn.set_all_custom_widgets_to_(child, state)

    @classmethod
    def enable_custom_widget_when_(cls, widget, condition: Union[Condition, Conditions, bool]):
        """有条件地启用控件"""
        # 设置控件状态
        if condition is True or hasattr(condition, "check") and condition.check():
            widget.set_state(cls.State.NORMAL)
        else:
            widget.set_state(cls.State.DISABLED)

    def _set_click_time(self, click_time):
        self._click_time = click_time

    def set_text(self, new_text):
        """用不同底层实现,设置文本的方式不同,需要重写"""
        self._text = new_text
        return self

    def _update_visual_state(self):
        """根据鼠标状态更新绘制"""
        if self._state == self.State.DISABLED:
            return

        if self._above:  # 鼠标在按钮上
            if self._down:
                self._draw(self.State.CLICKED)
            else:
                self._draw(self.State.HOVERED)
        else:
            self._draw()  # 恢复常驻状态

    def _on_enter(self, _event=None):
        self._above = True
        self._update_visual_state()

    def _on_leave(self, _event=None):
        self._above = False
        self._update_visual_state()

    def _on_button_down(self, _event=None):
        self._down = True
        self._update_visual_state()

    def _on_button_up(self, _event=None):
        self._down = False
        self._update_visual_state()

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


class CustomCornerBtn(tk.Frame, CustomBtn):
    """
    基于Frame+Canvas的定制按钮, 可以设定宽高, 圆角, 边框, 边距等属性.
    当传入边距时, 会覆盖宽高的设置, 根据文本内容自动调整大小以适应边距. 边距只传入一个时, 会自适应调整宽高成方形按钮.
    """

    def __init__(self, parent, text="Button", corner_radius=4, width=100, height=30,
                 border_color='#D0D0D0', border_width=1, i_padx=None, i_pady=None, *args, **kwargs):
        super().__init__(parent, width=width, height=height, *args, **kwargs)
        self._init_custom_btn_attrs()
        self._text = text
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.border_color = border_color
        self.border_width = border_width
        self.i_padx = i_padx
        self.i_pady = i_pady

        # 内部 Canvas
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self._core_widget = self.canvas
        self._core_widget.pack(fill="both", expand=True)

        self.set_styles(self._default_styles)
        self.pack_propagate(False)  # 禁止根据子组件改变大小,因为Canvas依赖Frame大小,自适应会导致无限循环
        self.grid_propagate(False)  # 禁止根据子组件改变大小
        self.set_state(self.State.NORMAL)
        self._bind_event()

    def _draw(self, tmp_state=None):
        """根据当前状态重绘按钮"""
        state = tmp_state if isinstance(tmp_state, CustomBtn.State) else self._state
        self.canvas.delete("all")
        w, h, tx, ty = self._auto_resize_by_text()
        r = min(self.corner_radius, h // 2, w // 2)
        bg = self._styles[state]['bg']
        fg = self._styles[state]['fg']
        bdc = self._styles[state]['bdc']

        CanvasUtils.draw_rounded_rect(
            canvas=self.canvas,
            x1=0, y1=0, x2=w, y2=h,
            radius=r,
            border_width=self.border_width,
            bg_color=bg,
            border_color=bdc
        )
        # 居中文本
        self.text_id = self.canvas.create_text(tx, ty, text=self._text, fill=fg)

    def _auto_resize_by_text(self):
        """如果有边距,会根据文本内容自动调整大小以适应边距"""

        def _try_unpack(v):
            # 可处理二元组,单个值或None
            try:
                a, b = v
                return int(a), int(b)
            except TypeError:
                try:
                    a = b = int(v) if v is not None else 0
                except TypeError:
                    a = b = 0
            return a, b

        # 用系统默认字体
        import tkinter.font
        font = tkinter.font.nametofont("TkDefaultFont")
        line_height = font.metrics("linespace")
        lines = self._text.split('\n')
        # 计算新的宽高
        pl, pr = _try_unpack(self.i_padx)
        if self.i_padx is not None:
            text_width = max(font.measure(line) for line in lines)
            w = text_width + pl + pr
            self.config(width=w)
        else:
            w = self.winfo_width()
        pt, pb = _try_unpack(self.i_pady)
        if self.i_pady is not None:
            text_height = len(lines) * line_height
            h = text_height + pt + pb
            self.config(height=h)
        else:
            h = self.winfo_height()
        # 计算文本居中锚点
        tx = (w + pl - pr) // 2
        ty = (h + pb - pt) // 2
        # print(w, h, tx, ty)
        # 如果只设置了垂直 padding（想生成正方形），则用 h 替代 w
        if self.i_padx is None and self.i_pady is not None:
            w = h
            tx = w // 2
            self.config(width=w)
        # 如果只设置了水平 padding，生成正方形
        elif self.i_pady is None and self.i_padx is not None:
            h = w
            ty = h // 2
            self.config(height=h)
        return w, h, tx, ty

    def set_corner_radius(self, radius):
        """
        设置固定圆角半径，然后立即重绘
        """
        self.corner_radius = radius
        return self

    def set_corner_scale(self, scale):
        """
        根据比例设置圆角，比例是相对于短边的（宽和高中更小的那个边）
        比如 scale=0.2 表示短边的 20%
        """
        short_edge = min(self.winfo_width(), self.winfo_height())
        radius = int(short_edge * scale)
        self.corner_radius = radius
        return self

    def set_border(self, width, color):
        """设置边框宽度和边框主颜色,若之后重新设置主颜色,边框颜色会被覆盖"""
        self.border_width = width
        brighten_color = ColorUtils.brighten_color(color)
        self._styles[self.State.HOVERED]['bdc'] = color
        self._styles[self.State.CLICKED]['bdc'] = brighten_color
        self._styles[self.State.SELECTED]['bdc'] = brighten_color
        return self

    def set_propagate(self, propagate: bool):
        """设置是否允许子组件改变大小"""
        self.pack_propagate(propagate)
        self.grid_propagate(propagate)
        return self


class CustomLabelBtn(tk.Label, CustomBtn):
    def __init__(self, parent, text, *args, **kwargs):
        self._init_custom_btn_attrs()
        super().__init__(parent, text=text, relief='flat', *args, **kwargs)
        self._text = text
        self.bind('<Enter>', self._on_enter, add='+')
        self.bind('<Leave>', self._on_leave, add='+')
        self.bind('<Button-1>', self._on_button_down, add='+')
        self.bind('<ButtonRelease-1>', self._on_button_up, add='+')
        self._core_widget = self

        self.set_styles(self._default_styles)
        self.set_state(self.State.NORMAL)

    def _draw(self, tmp_state=None):
        """根据当前状态更新样式"""
        state = tmp_state if isinstance(tmp_state, CustomBtn.State) else self._state
        self.configure(bg=self._styles[state]['bg'], fg=self._styles[state]['fg'])
        self.config(text=self._text)
