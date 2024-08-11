import os
import subprocess
import winreg

import psutil


def get_wechat_threads():
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] == 'WeChat.exe':
            return proc.threads()
    return []

def terminate_mutex_thread(threads):
    mutex_name = "WeChat App Instance Identity Mutex Name"
    for thread in threads:
        try:
            # 这里需要更复杂的逻辑来检查线程是否持有特定的互斥体
            # 这只是一个简化的示例
            if mutex_name in str(thread):
                thread.terminate()
                print(f"Terminated thread {thread.id}")
                return True
        except:
            pass
    return False

def get_wechat_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat")
        path = winreg.QueryValueEx(key, "InstallLocation")[0]
        winreg.CloseKey(key)
        return path
    except:
        return None

def run_wechat(path):
    if path:
        wechat_exe = os.path.join(path, "WeChat.exe")
        if os.path.exists(wechat_exe):
            subprocess.Popen(wechat_exe)
            print("WeChat started")
        else:
            print("WeChat.exe not found")
    else:
        print("WeChat installation path not found")

if __name__ == "__main__":
    threads = get_wechat_threads()
    if threads:
        if terminate_mutex_thread(threads):
            print("Mutex thread terminated")
        else:
            print("Mutex thread not found")
    else:
        print("WeChat process not found")

    wechat_path = get_wechat_path()
    run_wechat(wechat_path)


