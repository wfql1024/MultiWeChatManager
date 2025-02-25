from abc import ABC
from tkinter import ttk

from public_class.reusable_widget import SubToolWnd
from resources import Constants


class LoadingWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title):
        self.progress = None
        self.label = None

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.LOADING_WND_SIZE

    def set_wnd(self):
        self.wnd.resizable(False, False)

    def load_content(self):
        self.label = ttk.Label(self.wnd, text="正在载入，请稍等……")
        self.label.pack(pady=Constants.T_PAD_Y)
        self.progress = ttk.Progressbar(self.wnd, mode="determinate", length=Constants.LOADING_PRG_LEN)
        self.progress.pack(pady=Constants.T_PAD_Y)

        self.progress.start(15)

    def auto_close(self):
        if self.wnd.winfo_exists():
            self.progress.stop()
            self.progress['value'] = self.progress['maximum']
            self.wnd.update_idletasks()
            self.wnd.destroy()
