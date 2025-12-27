import os
import re

from data_access import RemoteSw, LocalSetting
from public.enums import RemoteSwKey, LocalSettingKey
from utils.logger_utils import Logger


class SwInfoFuncImpl:
    id = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        name = cls.__name__
        suffix = "InfoFuncImpl"
        if name.endswith(suffix):
            cls.id = name[:-len(suffix)]
        else:
            cls.id = name

    @staticmethod
    def get_curr_login_acc_from_config_file():
        """获取当前登录的账号"""
        return None

    @staticmethod
    def get_curr_login_acc_avatar_paths():
        """获取当前登录账号的头像路径"""
        return []


class WeChatInfoFuncImpl(SwInfoFuncImpl):

    @classmethod
    def get_curr_login_acc_from_config_file(cls):
        from func_core.sw_func_core import SwInfoFuncCore
        # Printer().debug("进入微信的查找当前微信ID的方法")
        config_addresses, = RemoteSw().get_(cls.id, **{RemoteSwKey.CONFIG_ADDRESSES: None})
        if not isinstance(config_addresses, list) or len(config_addresses) == 0:
            return None
        config_address = config_addresses[0]
        config_data_path = SwInfoFuncCore.resolve_sw_path(cls.id, config_address)
        if os.path.isfile(config_data_path):
            with open(config_data_path, 'r', encoding="utf-8", errors="ignore") as f:
                acc_info = f.read()
            # 获取文件中的最后四行
            str_line = ''.join(acc_info.strip().splitlines())
            acc_id_pattern = r'wxid_[a-zA-Z0-9_]+\\config'
            match = re.search(acc_id_pattern, str_line)
            if match:
                # 提取 wxid_……
                matched_str = match.group(0)
                wx_id = matched_str.split("\\")[0]  # 获取 wxid_...... 部分
                return wx_id
        return None

    @classmethod
    def get_curr_login_acc_avatar_paths(cls) -> list:
        """
                获取当前登录账号头像的WeChat实现
                在"%data_dir%/All Users"内, jpg文件即是当前登录账号的头像文件
                :return:
                """
        try:
            data_dir, = LocalSetting().get_(cls.id, **{LocalSettingKey.DATA_DIR: None})
            curr_acc_avatar_dir = os.path.join(data_dir, "All Users")
            return [os.path.join(curr_acc_avatar_dir, item).replace("\\", "/")
                    for item in os.listdir(curr_acc_avatar_dir) if item.endswith(".jpg")]
        except Exception as e:
            Logger().error(e)
        return []


class WeixinInfoFuncImpl(SwInfoFuncImpl):

    @classmethod
    def get_curr_login_acc_avatar_paths(cls) -> list:
        """
        获取当前登录账号头像的Weixin实现
        在"%data_dir%/all_users/head_imgs/0"内通常存放着当前头像的图片文件
        :return:
        """
        try:
            data_dir, = LocalSetting().get_(cls.id, **{LocalSettingKey.DATA_DIR: None})
            curr_acc_avatar_dir = os.path.join(data_dir, "all_users", "head_imgs", "0")
            return [os.path.join(curr_acc_avatar_dir, item).replace("\\", "/")
                    for item in os.listdir(curr_acc_avatar_dir)]
        except Exception as e:
            Logger().error(e)
        return []


class WXWorkInfoFuncImpl(SwInfoFuncImpl):

    @classmethod
    def get_curr_login_acc_avatar_paths(cls) -> list:
        """
        获取当前登录账号头像的WXWork实现
        在"%data_dir%/Global"内通常存放着qrcode_logo_user_ava开头的头像文件
        :return:
        """
        try:
            data_dir, = LocalSetting().get_(cls.id, **{LocalSettingKey.DATA_DIR: None})
            global_dir = os.path.join(data_dir, "Global")
            return [os.path.join(global_dir, f).replace('\\', '/')
                    for f in os.listdir(global_dir) if f.startswith("qrcode_login_user_ava")]
        except Exception as e:
            Logger().error(e)
        return []
