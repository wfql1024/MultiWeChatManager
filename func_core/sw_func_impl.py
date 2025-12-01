import os
import re


class SwInfoFuncImpl:
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_curr_wx_id_from_config_file(sw):
        return None


class WeChatSwInfoFuncImpl(SwInfoFuncImpl):
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_curr_wx_id_from_config_file(sw):
        from func_core.sw_func_core import SwInfoFuncCore
        # Printer().debug("进入微信的查找当前微信ID的方法")
        config_addresses, = RemoteSetting().get_(sw, config_addresses=None)
        if not isinstance(config_addresses, list) or len(config_addresses) == 0:
            return None
        config_address = config_addresses[0]
        config_data_path = SwInfoFuncCore.resolve_sw_path(sw, config_address)
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
