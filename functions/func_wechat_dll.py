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


def check_dll(mode):
    """检查当前的dll状态，判断是否为全局多开或者不可用"""
    dll_dir_path = func_setting.get_wechat_dll_dir_path()
    dll_path = os.path.join(dll_dir_path, "WeChatWin.dll")
    print("找到了dll文件")
    current_ver = func_setting.update_current_ver()
    try:
        # 以只读模式打开文件
        with open(dll_path, 'rb') as f:
            print("打开了dll文件")
            content = f.read()
        config_data = None
        # 判断文件是否存在
        if not os.path.exists(Config.VER_ADAPTATION_JSON_PATH):
            print(f"本地没有版本对照表, 正从此处下载： {Strings.VER_CONFIG_JSON}...")
            # 下载JSON文件并保存到指定位置
            try:
                # 设置2秒超时时间
                response = requests.get(Strings.VER_ADAPTATION_JSON, timeout=2)
                if response.status_code == 200:
                    try:
                        with open(Config.VER_ADAPTATION_JSON_PATH, 'w', encoding='utf-8') as config_file:
                            config_file.write(response.text)  # 将下载的JSON保存到文件
                        config_data = json.loads(response.text)  # 加载JSON数据
                    except Exception as e:
                        return f"错误：加载失败: {e}", None, None
                else:
                    return f"错误：获取失败: {response.status_code}", None, None
            except requests.exceptions.Timeout:
                return "错误：超时", None, None
            except Exception as e:
                return f"错误：{e}", None, None
        else:
            # 文件存在时，读取本地文件
            with open(Config.VER_ADAPTATION_JSON_PATH, 'r', encoding='utf-8') as f:
                try:
                    config_data = json.load(f)
                except Exception as e:
                    return f"错误：读取失败: {e}", None, None
        # 继续处理 config_data
        if not config_data:
            return "错误：没有数据", None, None
        result = "不可用"
        result1 = config_data[mode][current_ver]["STABLE"]["pattern"]
        result2 = config_data[mode][current_ver]["PATCH"]["pattern"]
        pattern1_hex_list = result1.split(',')
        pattern2_hex_list = result2.split(',')

        for i in range(len(pattern1_hex_list)):
            # 检查是否包含目标字节序列
            pattern1_hex = pattern1_hex_list[i]
            pattern2_hex = pattern2_hex_list[i]
            # 将十六进制字符串转换为二进制字节序列
            pattern1 = bytes.fromhex(pattern1_hex)
            pattern2 = bytes.fromhex(pattern2_hex)
            # 根据检测结果返回相应的状态
            has_pattern1 = pattern1 in content
            has_pattern2 = pattern2 in content
            if has_pattern1 and not has_pattern2:
                return "未开启", pattern1, pattern2
            elif has_pattern2 and not has_pattern1:
                return "已开启", pattern1, pattern2
            elif has_pattern1 and has_pattern2:
                result = "错误，匹配到多条", None, None
                continue
            else:
                result = "不可用", None, None
                continue
        return result
    except PermissionError as pe:
        return f"错误：权限不足，无法检查 DLL 文件。{pe}", None, None
    except FileNotFoundError as fe:
        return f"错误：未找到文件，请检查路径。{fe}", None, None
    except KeyError as ke:
        return f"错误，未找到{current_ver}的适配。{ke}", None, None
    except Exception as e:
        try:
            # 设置2秒超时时间
            response = requests.get(Strings.VER_ADAPTATION_JSON, timeout=2)
            if response.status_code == 200:
                try:
                    with open(Config.VER_ADAPTATION_JSON_PATH, 'w', encoding='utf-8') as config_file:
                        config_file.write(response.text)  # 将下载的JSON保存到文件
                    config_data = json.loads(response.text)  # 加载JSON数据
                except Exception as e:
                    return f"错误：加载失败: {e}", None, None
            else:
                return f"错误：获取失败: {response.status_code}", None, None
        except requests.exceptions.Timeout:
            return "错误：超时", None, None
        except Exception as e:
            return f"错误：{e}", None, None
        return f"错误: {str(e)}", None, None


def switch_dll(mode):
    """切换全局多开状态"""
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

            current_mode, stable_pattern, patch_pattern = check_dll(mode)

            if current_mode == "已开启":
                print(f"当前：{mode}已开启")
                pos = mmapped_file.find(patch_pattern)
                if pos != -1:
                    mmapped_file[pos:pos + len(patch_pattern)] = stable_pattern
                    print("替换完成")
                    result = False
                else:
                    print("未找到对应的HEX模式")
            elif current_mode == "未开启":
                print(f"当前：{mode}已开启")
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
    print(check_dll("multiple"))
