import os
import shutil
import time
from datetime import datetime
from tkinter import messagebox

from functions import func_setting, subfunc_wechat
from utils import handle_utils
from utils.handle_utils import close_window_by_name


def get_config_status_by_account(account, data_path) -> str:
    """
    通过账号的配置状态
    :param data_path: 微信数据存储路径
    :param account: 账号
    :return: 配置状态
    """
    if not data_path:
        return "无法获取配置路径"

    config_path = os.path.join(data_path, "All Users", "config", f"{account}.data")
    if os.path.exists(config_path):
        mod_time = os.path.getmtime(config_path)
        date = datetime.fromtimestamp(mod_time)
        return f"{date.month}-{date.day} {date.hour:02}:{date.minute:02}"
    else:
        return "无配置"


def use_config(account):
    """
    使用账号对应的登录配置
    :param account: 账号
    :return: 是否成功应用配置
    """
    data_path = func_setting.get_wechat_data_path()
    if not data_path:
        messagebox.showerror("错误", "无法获取WeChat数据路径")
        return False
    # 构建源文件和目标文件路径
    source_file = os.path.join(data_path, "All Users", "config", f"{account}.data")
    target_file = os.path.join(data_path, "All Users", "config", "config.data")

    # 确保目标目录存在
    os.makedirs(os.path.dirname(target_file), exist_ok=True)

    # 复制配置文件
    try:
        shutil.copy2(source_file, target_file)
    except Exception as e:
        print(f"复制配置文件失败: {e}")
        return False

    return True


def create_config(account):
    """
    创建账号的登录配置文件
    :param account: 账号
    :return: 是否创建成功
    """
    data_path = func_setting.get_wechat_data_path()
    if not data_path:
        messagebox.showerror("错误", "无法获取WeChat数据路径")
        return False

    source_path = os.path.join(data_path, 'All Users', 'config', 'config.data')

    dest_filename = f"{account}.data"
    dest_path = os.path.join(data_path, 'All Users', 'config', dest_filename)

    try:
        if os.path.exists(dest_path):
            os.remove(dest_path)

        shutil.copy2(source_path, dest_path, follow_symlinks=False)
        close_window_by_name("WeChatLoginWndForPC")

        messagebox.showinfo("成功", f"配置文件已生成：{dest_filename}")

        return True

    except Exception as e:
        messagebox.showerror("错误", f"生成配置文件时发生错误：{str(e)}")
        return False


def test(account, status):
    """
    尝试打开微信，让用户判断是否是对应的账号，根据用户结果去创建配置或结束
    :param account: 账号
    :param status: 是否全局多开状态
    :return: 是否对应
    """
    if messagebox.askyesno(
            "确认",
            "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
    ):
        subfunc_wechat.clear_idle_wnd_and_process()
        time.sleep(0.5)
        has_mutex_dict = subfunc_wechat.get_mutex_dict()
        sub_exe_process, _ = subfunc_wechat.open_wechat(status, has_mutex_dict)
        wechat_hwnd = handle_utils.wait_for_window_open("WeChatLoginWndForPC", timeout=8)
        if wechat_hwnd:
            if sub_exe_process:
                sub_exe_process.terminate()
            time.sleep(2)
            if messagebox.askyesno("确认", "是否为对应的微信号？"):
                return create_config(account)
            else:
                close_window_by_name("WeChatLoginWndForPC")
                return False
        else:
            messagebox.showerror("错误", "打开登录窗口失败")
    return False
