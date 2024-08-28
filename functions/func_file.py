import os
import shutil
from tkinter import messagebox

from functions import func_wechat_dll, func_setting
from resources import Config


def reset(initialization):
    # 显示确认对话框
    confirm = messagebox.askokcancel(
        "确认重置",
        "该操作将会关闭所有微信进程，清空头像、昵称、配置的路径等数据以及恢复到非全局模式，但不影响登录配置文件，请确认是否需要重置？"
    )
    directory_path = Config.PROJ_USER_PATH
    last_ver_path = func_setting.get_wechat_latest_version_path()
    if confirm:
        # 恢复原始的dll
        func_wechat_dll.switch_dll()

        dll_path = os.path.join(last_ver_path, "WeChatWin.dll")
        bak_path = os.path.join(last_ver_path, "WeChatWin.dll.bak")

        # 检查 .bak 文件是否存在
        if os.path.exists(bak_path):
            # 如果 WeChatWin.dll 存在，删除它
            if os.path.exists(dll_path):
                os.remove(dll_path)
                print(f"Deleted: {dll_path}")

            # 将 .bak 文件重命名为 WeChatWin.dll
            shutil.copyfile(bak_path, dll_path)
            print(f"Restored: {dll_path} from {bak_path}")
        else:
            print(f"No action needed. {bak_path} not found.")

        # 确认后删除目录的所有内容
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        messagebox.showinfo("重置完成", "目录已成功重置。")
        initialization()
    else:
        messagebox.showinfo("操作取消", "重置操作已取消。")
