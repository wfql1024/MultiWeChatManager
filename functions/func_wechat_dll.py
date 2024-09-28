import json
import mmap
import os
import shutil
import time
from tkinter import messagebox

import psutil
import requests
import winshell

from functions import func_setting
from resources import Strings, Config


def check_dll():
    """检查当前的dll状态，判断是否为全局多开或者不可用"""
    dll_dir_path = func_setting.get_wechat_dll_dir_path()
    dll_path = os.path.join(dll_dir_path, "WeChatWin.dll")
    current_ver = func_setting.update_current_ver()
    try:
        # 以只读模式打开文件
        with open(dll_path, 'rb') as f:
            content = f.read()
        config_data = None
        # 判断文件是否存在
        if not os.path.exists(Config.VER_CONFIG_JSON_PATH):
            print(f"本地没有版本对照表, 正从此处下载： {Strings.VER_CONFIG_JSON}...")
            # 下载JSON文件并保存到指定位置
            try:
                # 设置2秒超时时间
                response = requests.get(Strings.VER_CONFIG_JSON, timeout=2)
                if response.status_code == 200:
                    try:
                        with open(Config.VER_CONFIG_JSON_PATH, 'w', encoding='utf-8') as config_file:
                            config_file.write(response.text)  # 将下载的JSON保存到文件
                        config_data = json.loads(response.text)  # 加载JSON数据
                    except Exception as e:
                        return f"错误：加载失败: {e}"
                else:
                    return f"错误：获取失败: {response.status_code}"
            except requests.exceptions.Timeout:
                return "错误：超时"
            except Exception as e:
                return f"错误：{e}"
        else:
            # 文件存在时，读取本地文件
            with open(Config.VER_CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
                try:
                    config_data = json.load(f)
                except Exception as e:
                    return f"错误：读取失败: {e}"
        # 继续处理 config_data
        if not config_data:
            return "错误：没有数据"
        # 检查是否包含目标字节序列
        pattern1_hex = config_data[current_ver]["STABLE"]["pattern"]
        pattern2_hex = config_data[current_ver]["PATCH"]["pattern"]
        # 将十六进制字符串转换为二进制字节序列
        pattern1 = bytes.fromhex(pattern1_hex)
        pattern2 = bytes.fromhex(pattern2_hex)
        # 根据检测结果返回相应的状态
        has_pattern1 = pattern1 in content
        has_pattern2 = pattern2 in content
        if has_pattern1 and not has_pattern2:
            return "未开启"
        elif has_pattern2 and not has_pattern1:
            return "已开启"
        elif has_pattern1 and has_pattern2:
            return "错误：匹配到多条"
        else:
            return "不可用"
    except PermissionError:
        return "错误：权限不足，无法检查 DLL 文件。"
    except FileNotFoundError:
        return "错误：未找到 DLL 文件，请检查路径。"
    except Exception as e:
        try:
            # 设置2秒超时时间
            response = requests.get(Strings.VER_CONFIG_JSON, timeout=2)
            if response.status_code == 200:
                try:
                    with open(Config.VER_CONFIG_JSON_PATH, 'w', encoding='utf-8') as config_file:
                        config_file.write(response.text)  # 将下载的JSON保存到文件
                    config_data = json.loads(response.text)  # 加载JSON数据
                except Exception as e:
                    return f"错误：加载失败: {e}"
            else:
                return f"错误：获取失败: {response.status_code}"
        except requests.exceptions.Timeout:
            return "错误：超时"
        except Exception as e:
            return f"错误：{e}"
        return f"错误: {str(e)}"


def switch_dll():
    """切换dll状态"""
    # 尝试终止微信进程
    wechat_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.name().lower() == 'wechat.exe':
            wechat_processes.append(proc)

    if wechat_processes:
        print("发现正在运行的微信进程，尝试关闭...")
        for proc in wechat_processes:
            try:
                proc.terminate()
            except psutil.AccessDenied:
                print(f"无法终止进程 {proc.pid}，可能需要管理员权限。")
            except Exception as e:
                print(f"终止进程 {proc.pid} 时出错: {str(e)}")

        # 等待进程完全关闭
        time.sleep(2)

        # 检查是否所有进程都已关闭
        still_running = [p for p in wechat_processes if p.is_running()]
        if still_running:
            print("警告：以下微信进程仍在运行：")
            for p in still_running:
                print(f"PID: {p.pid}")
            print("请手动关闭这些进程后再继续。")
            return False

    # 获取 DLL 路径
    dll_dir_path = func_setting.get_wechat_dll_dir_path()
    # 获取桌面路径
    desktop_path = winshell.desktop()
    # 定义目标路径和文件名
    dll_path = os.path.join(dll_dir_path, "WeChatWin.dll")
    bak_path = os.path.join(dll_dir_path, "WeChatWin.dll.bak")
    bak_desktop_path = os.path.join(desktop_path, "WeChatWin.dll.bak")
    current_ver = func_setting.update_current_ver()

    try:
        with open(dll_path, 'r+b') as f:
            result = None
            mmapped_file = mmap.mmap(f.fileno(), 0)

            config_data = None
            response = requests.get(Strings.VER_CONFIG_JSON)
            try:
                if response.status_code == 200:
                    config_data = json.loads(response.text)
            except Exception as e:
                print(f"Failed to fetch config: {e}, {response.status_code}")

            stable_pattern_hex = config_data[current_ver]["STABLE"]["pattern"]
            patch_pattern_hex = config_data[current_ver]["PATCH"]["pattern"]

            stable_pattern = bytes.fromhex(stable_pattern_hex)
            patch_pattern = bytes.fromhex(patch_pattern_hex)

            current_mode = check_dll()

            if current_mode == "已开启":
                print("当前是全局模式")
                pos = mmapped_file.find(patch_pattern)
                if pos != -1:
                    mmapped_file[pos:pos + len(patch_pattern)] = stable_pattern
                    print("替换完成")
                    result = False
                else:
                    print("未找到对应的HEX模式")
            elif current_mode == "未开启":
                print("当前是稳定模式")
                if not os.path.exists(bak_path):
                    messagebox.showinfo("提醒",
                                        "当前是您首次切换模式，已将原本的WeChatWin.dll拷贝为WeChatWin.dll.bak，并也拷贝到桌面，可另外备份保存。")
                    shutil.copyfile(dll_path, bak_path)
                    shutil.copyfile(dll_path, bak_desktop_path)
                pos = mmapped_file.find(stable_pattern)
                if pos != -1:
                    mmapped_file[pos:pos + len(stable_pattern)] = patch_pattern
                    print("替换完成")
                    result = True
                else:
                    print("未找到对应的HEX模式")
            else:
                print("非法操作")

            mmapped_file.flush()
            mmapped_file.close()

        print("所有操作完成")
        return result

    except PermissionError:
        print("权限不足，无法修改 DLL 文件。请以管理员身份运行程序。")
        return result
    except Exception as e:
        print(f"修改 DLL 文件时出错: {str(e)}")
        return result


if __name__ == "__main__":
    print(check_dll())
