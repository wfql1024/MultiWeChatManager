import base64
import os
import time
from typing import Union, Tuple, List

import psutil
from PIL import Image

from functions import func_setting, func_wechat_dll, subfunc_file
from resources.config import Config
from resources.strings import Strings
from utils import process_utils, string_utils


def get_acc_avatar_from_files(account):
    """
    从本地缓存获取头像
    :param account: 原始微信号
    :return: 头像文件 -> ImageFile
    """

    # 构建头像文件路径
    avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{account}", f"{account}.jpg")

    # 检查是否存在对应account的头像
    if os.path.exists(avatar_path):
        return Image.open(avatar_path)

    # 如果没有，检查default.jpg
    default_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")
    if os.path.exists(default_path):
        return Image.open(default_path)

    # 如果default.jpg也不存在，则将从字符串转换出来
    try:
        base64_string = Strings.DEFAULT_AVATAR_BASE64
        image_data = base64.b64decode(base64_string)
        with open(default_path, "wb") as f:
            f.write(image_data)
        return Image.open(default_path)
    except FileNotFoundError as e:
        print("文件路径无效或无法创建文件:", e)
    except IOError as e:
        print("图像文件读取失败:", e)
    except Exception as e:
        print("所有方法都失败，创建空白头像:", e)
        return Image.new('RGB', (44, 44), color='white')


def get_account_display_name(account) -> str:
    """
    获取账号的展示名
    :param account: 微信账号
    :return: 展示在界面的名字
    """
    # 依次查找 note, nickname, alias，找到第一个不为 None 的值
    display_name = account  # 默认值为 account
    for key in ("note", "nickname", "alias"):
        value = subfunc_file.get_acc_details_from_acc_json(account, **{key: None})[0]
        if value is not None:
            display_name = value
            break

    return string_utils.balanced_wrap_text(display_name, 10)


def get_account_list() -> Union[Tuple[None, None, None], Tuple[list, List[str], list]]:
    """
    获取账号及其登录情况

    :Returns: ["已登录账号"]，["未登录账号"]，[("已登录进程", int(账号))]
    """

    def update_acc_list_by_pid(process_id: int):
        """
        为存在的微信进程匹配出对应的账号，并更新[已登录账号]和[(已登录进程,账号)]
        :param process_id: 微信进程id
        :return: 无
        """
        try:
            # 获取指定进程的内存映射文件路径
            for f in psutil.Process(process_id).memory_maps():
                print(f)
                # 将路径中的反斜杠替换为正斜杠
                normalized_path = f.path.replace('\\', '/')
                # 检查路径是否以 data_path 开头
                if normalized_path.startswith(data_path):
                    print(
                        f"┌———匹配到进程{process_id}使用的符合的文件，待对比，已用时：{time.time() - start_time:.4f}秒")
                    print(f"提取中：{f.path}")
                    path_parts = f.path.split(os.path.sep)
                    try:
                        wxid_index = path_parts.index(os.path.basename(data_path)) + 1
                        wxid = path_parts[wxid_index]
                        wechat_processes.append((wxid, process_id))
                        logged_in_wxids.add(wxid)
                        print(f"└———提取到进程{process_id}对应账号{wxid}，已用时：{time.time() - start_time:.4f}秒")
                        break
                    except ValueError:
                        pass
        except psutil.AccessDenied:
            print(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            print(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            print(f"发生意外错误: {e}")

    start_time = time.time()
    data_path = func_setting.get_wechat_data_path()
    if not data_path:
        return None, None, None

    wechat_processes = []
    logged_in_wxids = set()

    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    print(f"读取到微信所有进程，用时：{time.time() - start_time:.4f} 秒")
    if len(pids) != 0:
        for pid in pids:
            update_acc_list_by_pid(pid)
    print(f"完成判断进程对应账号，用时：{time.time() - start_time:.4f} 秒")

    # 获取文件夹并分类
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders
    logged_in = list(logged_in_wxids & folders)
    not_logged_in = list(folders - logged_in_wxids)

    print(f"logged_in：{logged_in}")
    print(f"not_logged_in：{not_logged_in}")
    print(f"完成账号分类，用时：{time.time() - start_time:.4f} 秒")

    # 更新数据
    status, _, _ = func_wechat_dll.check_dll("multiple")
    pid_dict = dict(wechat_processes)
    if status == "已开启":
        for acc in logged_in + not_logged_in:
            print(f"由于是全局多开模式，直接所有has_mutex都为false")
            subfunc_file.update_acc_details_to_acc_json(acc, pid=pid_dict.get(acc, None), has_mutex=False)
    else:
        for acc in logged_in + not_logged_in:
            pid = pid_dict.get(acc, None)
            if pid is None:
                subfunc_file.update_acc_details_to_acc_json(acc, has_mutex=None)
            subfunc_file.update_acc_details_to_acc_json(acc, pid=pid_dict.get(acc, None))
        # 更新json表中各微信进程的互斥体情况
        subfunc_file.update_has_mutex_from_all_wechat()

    print(f"完成记录账号对应pid，用时：{time.time() - start_time:.4f} 秒")

    return logged_in, not_logged_in, wechat_processes


if __name__ == '__main__':
    # note = subfunc_file.get_acc_details_from_acc_json('wxid_t2dchu5zw9y022', note=None)[0]
    # print(note)
    for f in psutil.Process(36100).open_files():
        print(f.path)
