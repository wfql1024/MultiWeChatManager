import os
import re

from functions import subfunc_file
from functions.sw_func import SwInfoFunc
from public.config import Config
from utils import image_utils
from utils.logger_utils import mylogger as logger


class AccInfoFuncImpl:
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_avatar_url_from_file(sw, acc_list, data_dir):
        return False

    @staticmethod
    def get_nickname_from_file(sw, acc_list, data_dir):
        return False

    @staticmethod
    def get_curr_wx_id_from_config_file(sw):
        return None


class WeChatAccInfoFuncImpl(AccInfoFuncImpl):
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_avatar_url_from_file(sw, acc_list, data_dir):
        changed = False

        for acc in acc_list:
            acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
            # print(acc_info_dat_path)
            if not os.path.isfile(acc_info_dat_path):
                continue
            with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
                acc_info = f.read()
            # 获取文件内容，去掉多余的换行符
            info_line = '\n'.join(acc_info.strip().splitlines())
            # 定义正则表达式来匹配 https 开头并以 /0 或 /132 结尾的 URL
            url_patterns = [r'https://[^\s]*?/0', r'https://[^\s]*?/132']
            # 使用正则表达式查找匹配的 URL
            matched_url = None
            for p in url_patterns:
                match = re.search(p, info_line)
                if match:
                    matched_url = match.group(0)  # 获取匹配的 URL
                    # logger.info("Found URL:", matched_url)
                    break
                else:
                    # logger.warning("No matching URL found.")
                    pass
            if matched_url and matched_url.endswith('/132'):
                matched_url = matched_url.rstrip('/132') + '/0'
            if matched_url:
                avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg")
                logger.info(f"{acc}: {matched_url}")
                success = image_utils.download_image(matched_url, avatar_path)
                if success is True:
                    subfunc_file.update_sw_acc_data(sw, acc, avatar_url=matched_url)
                    changed = True
        return changed

    @staticmethod
    def get_nickname_from_file(sw, acc_list, data_dir):
        changed = False
        for acc in acc_list:
            acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
            if not os.path.isfile(acc_info_dat_path):
                continue
            with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
                acc_info = f.read()
            # 获取文件
            str_line = ''.join(acc_info.strip().splitlines())
            # print(f"最后四行：{str_line}")
            nickname_str_pattern = rf'{acc}(.*?)https://'
            match = re.search(nickname_str_pattern, str_line)
            if match:
                matched_str = match.group(1)
                cleaned_str = re.sub(r'[0-9a-fA-F]{32}.*', '', matched_str)
                cleaned_str = re.sub(r'\x1A.*?\x12', '', cleaned_str)
                cleaned_str = re.sub(r'[^\x20-\x7E\xC0-\xFF\u4e00-\u9fa5]+', '', cleaned_str)
                success = subfunc_file.update_sw_acc_data(sw, acc, nickname=cleaned_str)
                if success is True:
                    changed = True
        return changed

    @staticmethod
    def get_curr_wx_id_from_config_file(sw):
        # Printer().debug("进入微信的查找当前微信ID的方法")
        config_addresses, = subfunc_file.get_remote_cfg(sw, config_addresses=None)
        if not isinstance(config_addresses, list) or len(config_addresses) == 0:
            return None
        config_address = config_addresses[0]
        config_data_path = SwInfoFunc.resolve_sw_path(sw, config_address)
        if os.path.isfile(config_data_path):
            with open(config_data_path, 'r', encoding="utf-8", errors="ignore") as f:
                acc_info = f.read()
            # 获取文件中的最后四行
            str_line = ''.join(acc_info.strip().splitlines())
            wxid_pattern = r'wxid_[a-zA-Z0-9_]+\\config'
            match = re.search(wxid_pattern, str_line)
            if match:
                # 提取 wxid_……
                matched_str = match.group(0)
                wx_id = matched_str.split("\\")[0]  # 获取 wxid_...... 部分
                return wx_id
        return None
