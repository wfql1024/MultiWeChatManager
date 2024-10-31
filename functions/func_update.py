# 获取最新版本号
import os
import subprocess
import zipfile

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


def create_and_execute_bat(current_version, zip_path, current_exe_path):
    bat_content = f"""@echo off
chcp 65001 >nul  :: 设置代码页为 UTF-8，避免乱码
setlocal


tasklist /FI "WINDOWTITLE eq 微信多开管理器" | find /I "微信多开管理器" >nul
if %errorlevel% == 0 (
    taskkill /F /IM "当前程序.exe"
)


set "version_folder={current_version}"
set "program_folder=%~dp0"
mkdir "%program_folder%%version_folder%"
move "%program_folder%*" "%program_folder%%version_folder%\\" /Y


set "zip_path={zip_path}"
powershell -command "Expand-Archive -Path '%zip_path%' -DestinationPath '%program_folder%' -Force"


set "user_files_folder=%program_folder%%version_folder%\\user_files"
set "external_res_folder=%program_folder%external_res"

if exist "%user_files_folder%" (
    xcopy "%user_files_folder%" "%program_folder%user_files" /E /I /Y
)

:: 5. 强制删除当前 exe 文件（如果程序仍在运行，删除会失败）
del /F /Q "{current_exe_path}"

:: 6. 打开新的 exe 程序
start "" "%program_folder%新的程序.exe"

endlocal
"""

    bat_file_path = os.path.join(os.path.dirname(__file__), 'update.bat')

    # 写入内容到 .bat 文件
    with open(bat_file_path, 'w', encoding='utf-8') as bat_file:
        bat_file.write(bat_content)

    # 执行 .bat 文件
    subprocess.run([bat_file_path], shell=True)


if __name__ == '__main__':
    # 解压更新
    update_zip = r"C:\Users\25359\AppData\Local\Temp\tmpu_tm66gw\temp.zip"
    tmp_dir = os.path.dirname(update_zip)
    with zipfile.ZipFile(update_zip, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)
    # create_and_execute_bat(
    #     "2.5.0.410",
    #     r"C:\Users\25359\AppData\Local\Temp\tmpa75gt106\temp.zip",
    #     r"E:\Now\Inbox\测试\微信多开管理器 v2.4.0.365 Alpha")
