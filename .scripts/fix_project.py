# import os
# SRGB_PROFILE = r"C:\Windows\System32\spool\drivers\color\sRGB Color Space Profile.icm"
import sys
import tkinter as tk
# from PIL import Image, ImageTk

# def fix_image_srgb_profile_in_project(root_dir="."):
#     """
#     遍历指定目录下的所有 .png 文件，去掉错误的 sRGB profile
#     :param root_dir: 项目根目录（默认当前目录）
#     """
#     with open(SRGB_PROFILE, "rb") as f:
#         srgb_profile = f.read()
#     for dirpath, _, filenames in os.walk(root_dir):
#         for filename in filenames:
#             if filename.lower().endswith(".png"):
#                 file_path = os.path.join(dirpath, filename)
#                 try:
#                     img = Image.open(file_path)
#                     img.save(file_path, icc_profile=srgb_profile)  # 去掉 profile
#                     print(f"已修复: {file_path}")
#                 except Exception as e:
#                     print(f"跳过 {file_path}, 错误: {e}")



def suppress_libpng_warnings():
    """屏蔽 libpng 的 iCCP 警告"""
    class _StderrFilter:
        def __init__(self, stream):
            self.stream = stream
        def write(self, message):
            if "libpng warning: iCCP: known incorrect sRGB profile" in message:
                return  # 屏蔽掉这个警告
            self.stream.write(message)
        def flush(self):
            self.stream.flush()
    sys.stderr = _StderrFilter(sys.stderr)


def main():
    root = tk.Tk()
    root.title("Pillow + Tkinter Test")

    # # 打开 PNG 图片并转成 Tkinter 可显示的对象
    # img = Image.open(r"..\external_res\Feedback.png")
    # tk_img = ImageTk.PhotoImage(img)
    #
    # # 放到 Label 上显示
    # lbl = tk.Label(root, image=tk_img)
    # lbl.pack()

    # 输入框，用来测试输入法切换时是否触发警告
    entry = tk.Entry(root, width=30)
    entry.pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    # fix_image_srgb_profile_in_project("..")  # 当前目录的上一级
    # suppress_libpng_warnings()
    main()