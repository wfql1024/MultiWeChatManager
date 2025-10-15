if __name__ == "__main__":
    import tkinter as tk
    import pystray
    from tkinter import ttk
    from PIL import Image
    from resources import Config

    root = tk.Tk()
    root.overrideredirect(True)  # 隐藏标题栏


    def exit_action(icon, item):
        icon.stop()


    def show_window(icon, item):
        root.update_idletasks()
        root.deiconify()


    def hide_window(icon, item):
        root.withdraw()


    image = Image.open(Config.PROJ_ICO_PATH)  # 使用自定义图标
    icon = pystray.Icon("name", image, "Title")
    icon.run()