import tkinter as tk


def create_window():
    root = tk.Tk()
    root.title("更新程序")

    label = tk.Label(root, text="测试内容", font=("Arial", 20))
    label.pack(padx=20, pady=20)

    # 运行窗口的主循环
    root.mainloop()


if __name__ == "__main__":
    create_window()
