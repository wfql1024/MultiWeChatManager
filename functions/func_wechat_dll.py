import mmap
import os
import time

import psutil

from functions import func_setting


def check_dll():
    dll_path = os.path.join(func_setting.get_wechat_latest_version_path(), "WeChatWin.dll")
    try:
        # 以只读模式打开文件
        with open(dll_path, 'rb') as f:
            content = f.read()

        # 检查是否包含目标字节序列
        pattern1 = b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'
        pattern2 = b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'

        has_pattern1 = pattern1 in content
        has_pattern2 = pattern2 in content

        # 根据检测结果返回相应的状态
        if has_pattern1 and not has_pattern2:
            return "未开启"
        elif has_pattern2 and not has_pattern1:
            return "已开启"
        else:
            return "不可用"

    except PermissionError:
        return "权限不足，无法检查 DLL 文件。"

    except FileNotFoundError:
        return "未找到 DLL 文件，请检查路径。"

    except Exception as e:
        return f"发生错误: {str(e)}"


def switch_dll():
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
    dll_path = os.path.join(func_setting.get_wechat_latest_version_path(), "WeChatWin.dll")

    try:
        with open(dll_path, 'r+b') as f:
            result = None
            mmapped_file = mmap.mmap(f.fileno(), 0)
            stable_pattern = b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'
            patch_pattern = b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'

            current_mode = check_dll()

            if current_mode == "已开启":
                print("当前是补丁模式")
                pos = mmapped_file.find(patch_pattern)
                if pos != -1:
                    mmapped_file[pos:pos + len(patch_pattern)] = stable_pattern
                    print("替换完成")
                    result = False
                else:
                    print("未找到对应的HEX模式")
            elif current_mode == "未开启":
                print("当前是稳定模式")
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
