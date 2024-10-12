# 获取最新版本号
import os
import re
import tempfile
from tkinter import messagebox

import requests


def get_latest_version(url):
    try:
        # 请求Gitee仓库页面
        response = requests.get(url)
        if response.status_code == 200:
            print("访问页面成功")
            # 正则匹配符合命名格式的文件名，提取版本号
            match = re.search(
                r'MultiWeChatManager_x64_v(\d+\.\d+\.\d+\.\d+)([^\s]*).zip', response.text)
            if match:
                # 提取版本号部分
                version_number = match.group(1)  # 提取v后面的数字部分
                full_version = f"v{version_number}{match.group(2)}"  # 完整版本（包括v和后缀）
                return version_number, full_version  # 返回完整版本
            else:
                messagebox.showerror("错误", "未找到最新版本信息")
                return None
        else:
            messagebox.showerror("错误", "无法获取最新版本信息")
            return None
    except Exception as e:
        messagebox.showerror("错误", f"请求过程中出现问题: {e}")
        return None


def download_files(file_urls, temp_dir, progress_callback):
    print("进入下载文件方法...")
    for idx, url in enumerate(file_urls):
        # file_name = os.path.join(temp_dir, os.path.basename(url))
        file_name = os.path.join(temp_dir, "MultiWeChatManager_x64_v2.5.0.411.Alpha.zip")
        print(f"Downloading to {file_name}")
        with requests.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            total_length = int(r.headers.get('content-length', 0))
            with open(file_name, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # 过滤掉保持连接的chunk
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress_callback(idx, len(file_urls), downloaded, total_length)

    print("All files downloaded successfully.")
    return True


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


if __name__ == '__main__':
    file_url = f"https://d.feijix.com/storage/files/2024/10/06/6/10172646/17281995030431.gz?t=67052ac9&rlimit=20&us=Ioo2xfdKuS&sign=e813036e84770a466a9686509c3f10a5&download_name=MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    file_url = f"https://d.feijix.com/storage/files/2024/10/06/6/10172646/17281995030431.gz?t=67052a0e&rlimit=20&us=z4FiCcDrRo&sign=6a4127c45ab443b6f4cc84dfd5afa9d8&download_name=MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    # file_url = f"https://gitee.com/wfql1024/MultiWeChatManagerDist/raw/master/MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    with requests.get(file_url, stream=True, allow_redirects=True) as r:
        open(r"E:\Now\Inbox\test\MultiWeChatManager_x64_v2.5.0.411.Alpha.zip", 'wb').write(r.content)
