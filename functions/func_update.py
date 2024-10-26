# 获取最新版本号
import os
import re
import tempfile
import time
from tkinter import messagebox

import requests

from functions import subfunc_file
from utils import file_utils


def split_versions_by_current(current_ver):
    try:
        config_data = subfunc_file.fetch_config_data()
        if not config_data:
            print("没有数据")
            return "错误：没有数据"
        else:
            # 获取 update 节点的所有版本
            all_versions = list(config_data["update"].keys())
            # 对版本号进行排序
            sorted_versions = file_utils.get_sorted_full_versions(all_versions)
            if len(sorted_versions) == 0:
                return [], []
            # 遍历 sorted_versions，通过 file_utils.get_newest_full_version 比较
            for i, version in enumerate(sorted_versions):
                if file_utils.get_newest_full_version([current_ver, version]) == current_ver:
                    # 如果找到第一个不高于 current_ver 的版本
                    lower_or_equal_versions = sorted_versions[i:]
                    higher_versions = sorted_versions[:i]
                    break
            else:
                # 如果没有找到比 current_ver 小或等于的版本，所有都更高
                higher_versions = sorted_versions
                lower_or_equal_versions = []
            return higher_versions, lower_or_equal_versions

    except Exception as e:
        print(f"发生错误：{str(e)}")
        return "错误：无法获取版本信息"


def download_files(file_urls, download_dir, progress_callback):
    try:
        print("进入下载文件方法...")
        for idx, url in enumerate(file_urls):
            print(f"Downloading to {download_dir}")
            with requests.get(url, stream=True, allow_redirects=True) as r:
                r.raise_for_status()
                total_length = int(r.headers.get('content-length', 0))
                with open(download_dir, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:  # 过滤掉保持连接的chunk
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress_callback(idx, len(file_urls), downloaded, total_length)
        print("All files downloaded successfully.")
        return True
    except Exception as e:
        print(e)
        raise e


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
    # 设置环境变量，告诉 Python 不使用代理
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    os.environ['no_proxy'] = '*'
    print(split_versions_by_current("v2.7.0.411.Alpha"))
    # file_url = f"https://d.feijix.com/storage/files/2024/10/06/6/10172646/17281995030431.gz?t=67052ac9&rlimit=20&us=Ioo2xfdKuS&sign=e813036e84770a466a9686509c3f10a5&download_name=MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    # file_url = f"https://d.feijix.com/storage/files/2024/10/06/6/10172646/17281995030431.gz?t=670f77dc&rlimit=20&us=ulApVrrrB0&sign=026566dbd74c8088d4b9958b87b2bbc9&download_name=MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    # file_url = f"https://gitee.com/wfql1024/MultiWeChatManagerDist/raw/master/MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    # file_url = "https://gitee.com/wfql1024/MultiWeChatManager/releases/download/v2.5.0.411.Alpha/MultiWeChatManager_x64_v2.5.0.411.Alpha.zip"
    # current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
    # if not os.path.exists(rf"E:\Now\Inbox\test{current_time}"):
    #     os.makedirs(rf"E:\Now\Inbox\test{current_time}")
    # with requests.get(file_url, stream=True, allow_redirects=True) as r:
    #     open(rf"E:\Now\Inbox\test{current_time}\MultiWeChatManager_x64_v2.5.0.411.Alpha.zip", 'wb').write(r.content)
