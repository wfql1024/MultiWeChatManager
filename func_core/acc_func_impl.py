import os
import re

from data_access.setting import SwAccData, RootSetting
from utils import image_utils
from utils.logger_utils import Logger, Printer


class AccInfoFuncImpl:
    id = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        name = cls.__name__
        suffix = "AccInfoFuncImpl"
        if name.endswith(suffix):
            cls.id = name[:-len(suffix)]
        else:
            cls.id = name

    @classmethod
    def get_acc_avatar_from_file(cls, acc_list, data_dir):
        return False

    @classmethod
    def get_acc_nickname_from_file(cls, acc_list, data_dir):
        return False


class WeChatAccInfoFuncImpl(AccInfoFuncImpl):
    @classmethod
    def get_acc_avatar_from_file(cls, acc_list, data_dir):
        changed = False

        user_dir = RootSetting().user_dir
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
                avatar_path = os.path.join(user_dir, cls.id, f"{acc}", f"{acc}.jpg")
                Logger().info(f"{acc}: {matched_url}")
                success = image_utils.download_image(matched_url, avatar_path)
                if success is True:
                    SwAccData().update_(cls.id, acc, avatar_url=matched_url)
                    changed = True
        return changed

    @classmethod
    def get_acc_nickname_from_file(cls, acc_list, data_dir):
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
                success = SwAccData().update_(cls.id, acc, nickname=cleaned_str)
                Printer().print_vn(f"从配置文件获取到昵称: {cleaned_str}")
                if success is True:
                    changed = True
        return changed
