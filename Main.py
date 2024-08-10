# Main.py
import tkinter as tk
from main_window import MainWindow
from loading_window import LoadingWindow


def main():
    root = tk.Tk()
    loading_window = LoadingWindow(root)
    MainWindow(root, loading_window)
    root.mainloop()


if __name__ == "__main__":
    main()
