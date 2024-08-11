# main.py
import tkinter as tk

from ui.loading_ui import LoadingWindow
from ui.main_ui import MainWindow


def main():
    root = tk.Tk()
    loading_window = LoadingWindow(root)
    MainWindow(root, loading_window)
    root.mainloop()


if __name__ == "__main__":
    main()
