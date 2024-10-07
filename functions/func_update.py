# 获取最新版本号
import os
import tempfile
from tkinter import messagebox

import requests


# def get_latest_version(url):
#     response = requests.get(url)
#     if response.status_code == 200:
#         return response.text.strip()
#     else:
#         messagebox.showerror("错误", "无法获取最新版本信息")
#         return None
#
#
# # 下载文件
# def download_files(file_urls, temp_dir, progress_callback):
#     for idx, file_url in enumerate(file_urls):
#         file_name = os.path.join(temp_dir, os.path.basename(file_url))
#         with requests.get(file_url, stream=True) as r:
#             r.raise_for_status()
#             total_length = int(r.headers.get('content-length', 0))
#             with open(file_name, 'wb') as f:
#                 downloaded = 0
#                 for chunk in r.iter_content(chunk_size=8192):
#                     f.write(chunk)
#                     downloaded += len(chunk)
#                     progress_callback(idx, len(file_urls), downloaded, total_length)
#     return True
#
#
# # 更新进度条
# def update_progress(idx, total_files, downloaded, total_length):
#     percentage = (downloaded / total_length) * 100 if total_length else 0
#     progress_var.set(f"下载文件 {idx + 1}/{total_files}: {percentage:.2f}% 完成")
#     progress_bar['value'] = percentage
#     root.update_idletasks()
#
#
# # 下载窗口
# def show_download_window(file_urls, temp_dir):
#     download_window = tk.Toplevel(root)
#     download_window.title("下载更新")
#
#     global progress_var, progress_bar
#     progress_var = tk.StringVar(value="开始下载...")
#     tk.Label(download_window, textvariable=progress_var).pack(pady=10)
#
#     progress_bar = ttk.Progressbar(download_window, orient="horizontal", length=300, mode="determinate")
#     progress_bar.pack(pady=10)
#
#     tk.Button(download_window, text="关闭并更新", command=lambda: start_update_process(temp_dir)).pack(pady=10)
#
#     # 开始下载文件（多线程）
#     threading.Thread(target=download_files, args=(file_urls, temp_dir, update_progress)).start()
#
#
# # 启动更新进程
# def start_update_process(temp_dir):
#     # 新进程执行更新，删除旧文件，拷贝新文件并重启
#     update_script = f"""
# import os
# import shutil
# import sys
# import time
#
# old_dir = r'{sys.argv[0]}'
# new_dir = r'{temp_dir}'
#
# def replace_files():
#     time.sleep(2)  # 等待主程序退出
#     for item in os.listdir(new_dir):
#         s = os.path.join(new_dir, item)
#         d = os.path.join(old_dir, item)
#         if os.path.isfile(s):
#             shutil.copy2(s, d)
#         elif os.path.isdir(s):
#             shutil.copytree(s, d, dirs_exist_ok=True)
#     shutil.rmtree(new_dir)
#     os.startfile(old_dir)
#
# replace_files()
# """
#
#     # 写入临时脚本并启动新进程
#     update_file = os.path.join(temp_dir, 'update_script.py')
#     with open(update_file, 'w') as f:
#         f.write(update_script)
#     Popen([sys.executable, update_file])
#     root.quit()


# 主程序逻辑
def check_for_updates():
    # current_version = "1.0.0"  # 假设当前版本
    # latest_version = get_latest_version("http://example.com/version.txt")
    # if latest_version and latest_version != current_version:
    #     if messagebox.askyesno("更新可用", f"当前版本：{current_version}\n最新版本：{latest_version}\n是否立即更新？"):
    #         temp_dir = tempfile.mkdtemp()
    #         file_urls = ["http://example.com/file1.zip", "http://example.com/file2.zip"]  # 更新文件列表
    #         show_download_window(file_urls, temp_dir)
    # else:
    if True:
        messagebox.showinfo("提醒", f"当前已是最新版本。")