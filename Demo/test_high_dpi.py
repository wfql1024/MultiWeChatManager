from tkinter import *
from tkinter.ttk import *
import ctypes

ScaleFactor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
DPI_MODE = 2
'''修改DPI_MODE可以达到3种效果'''
if DPI_MODE == 0:
    ctypes.windll.shcore.SetProcessDpiAwareness(0)
elif DPI_MODE == 1 or DPI_MODE == 2:
    # 告诉操作系统使用程序自身的dpi适配
    ctypes.windll.shcore.SetProcessDpiAwareness(1)


def TkS(value) -> int:
    # 希望使用高分辨率效果时,用这个比率转换所有的点坐标
    # 使用 label.place(x=TkS(10), y=TkS(50), width=TkS(100), height=TkS(35)) 写法
    if DPI_MODE <= 1:
        return value
    elif DPI_MODE == 2:
        return int(ScaleFactor / 100 * value)


class WinGUI(Tk):
    def __init__(self):
        super().__init__()
        self.__win()
        global DPI_MODE
        if DPI_MODE == 0:
            # 窗口按照DPI比率拉大,像素变得模糊
            pass
        elif DPI_MODE == 1:
            # 窗口保持原本的像素比
            self.tk.call('tk', 'scaling', 96 / 72)
        elif DPI_MODE == 2:
            # 使用TkS拉伸窗口,窗口的像素尺寸
            self.tk.call('tk', 'scaling', 96 * ScaleFactor / 100 / 72)

        self.tk_label_lanxz4xb = self.__tk_label_lanxz4xb()
        self.tk_button_lanxzlhr = self.__tk_button_lanxzlhr()
        self.tk_input_lanxzxly = self.__tk_input_lanxzxly()
        self.tk_select_box_lany090g = self.__tk_select_box_lany090g()
        self.tk_button_lany0pqo = self.__tk_button_lany0pqo()

    def __win(self):
        self.title("小工具")
        # 设置窗口大小、居中
        width = TkS(400)
        height = TkS(300)
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
        self.geometry(geometry)
        self.resizable(width=False, height=False)

    def __tk_label_lanxz4xb(self):
        text = f"这是一个标签,{ScaleFactor}"
        label = Label(self, text=text)
        label.place(x=TkS(10), y=TkS(10), width=TkS(200), height=TkS(24))
        return label

    def __tk_button_lanxzlhr(self):
        btn = Button(self, text="按钮ABC")
        btn.place(x=TkS(290), y=TkS(10), width=TkS(100), height=TkS(36))
        return btn

    def __tk_input_lanxzxly(self):
        ipt = Entry(self)
        ipt.place(x=TkS(10), y=TkS(50), width=TkS(200), height=TkS(24))
        return ipt

    def __tk_select_box_lany090g(self):
        cb = Combobox(self, state="readonly")
        cb['values'] = ("列表框", "Python", "Tkinter Helper")
        cb.place(x=TkS(10), y=TkS(90), width=TkS(200), height=TkS(24))
        return cb

    def __tk_button_lany0pqo(self):
        btn = Button(self, text="按钮DEF")
        btn.place(x=TkS(290), y=TkS(60), width=TkS(100), height=TkS(36))
        return btn


class Win(WinGUI):
    def __init__(self):
        super().__init__()
        self.__event_bind()

    def TestABC(self, evt):
        print("<Button>事件未处理", evt)

    def TestDEF(self, evt):
        print("<Button>事件未处理", evt)

    def __event_bind(self):
        self.tk_button_lanxzlhr.bind('<Button>', self.TestABC)
        self.tk_button_lany0pqo.bind('<Button>', self.TestDEF)


if __name__ == "__main__":
    win = Win()
    win.mainloop()
