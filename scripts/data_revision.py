"""
本文件用以临时对json结构迭代
"""
from typing import List

from data_access.setting import SwCache, RemoteSw
from public.enums import RemoteSwKey
from utils.file_utils import DictUtils, JsonUtils


def v1_migrate_to_channels(data):
    """
    该方法是将远程配置v5版本的适配分支调整到v6格式
    将原来的 top-level feature/precise 迁移到各个渠道(channel)下的 feature/precise 中
    v5 版本结构:
    coexist
    ├── channel
    │   ├── default
    │   │   ├── label
    │   │   ├── introduce
    │   │   ├── author
    │   │   ├── exe_wildcard
    │   │   ├── sequence
    │   │   └── patch_wildcard
    │   └── default2
    │       ├── ...
    ├── feature
    │   ├── 4.1.0
    │   │   ├── default
    │   │   └── default2
    │   └── 4.0.6
    │       ├── default
    │       └── default2
    └── precise
        └── ...

    v6 版本结构:
    coexist
    ├── channel
    │   ├── default
    │   │   ├── label
    │   │   ├── ...
    │   │   ├── feature
    │   │   │   ├── 4.1.0
    │   │   │   └── 4.0.6
    │   │   └── precise
    │   │       └── 4.1.0
    │   └── default2
    │       ├── ...


    """
    channels = data.get("channels", {})
    top_feature = data.get("feature", {})
    top_precise = data.get("precise", {})

    for channel_name, channel_info in channels.items():
        # feature
        channel_feature = {}
        for version, versions_info in top_feature.items():
            if channel_name in versions_info:
                channel_feature[version] = versions_info[channel_name]
        if channel_feature:
            channel_info[RemoteSwKey.FEATURES_ADAPT] = channel_feature

        # precise
        channel_precise = {}
        for version, versions_info in top_precise.items():
            if channel_name in versions_info:
                channel_precise[version] = versions_info[channel_name]
        if channel_precise:
            channel_info[RemoteSwKey.PRECISES] = channel_precise

    return data


def v1_migrate_remote_data():
    # 原始数据 dict
    data = RemoteSw().load()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            original_data = RemoteSw().get_(sw, mode)
            if not isinstance(original_data, dict):
                continue
            new_data = v1_migrate_to_channels(original_data)
            data = RemoteSw().load()
            DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            JsonUtils.save_json(RemoteSw().get_file_path_from_root_cfg(), data)
            print(new_data)


def v1_migrate_cache_data():
    # 原始数据 dict
    data = SwCache().get_()
    sws = data.keys()
    for sw in sws:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            original_data = SwCache().get_(sw, mode)
            if not isinstance(original_data, dict):
                continue
            new_data = v1_migrate_to_channels(original_data)
            SwCache().update_(sw, **{mode: new_data})
            # data = RemoteSetting().load()
            # success = DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            # JsonUtils.save_json(RemoteSetting().get_file_path_from_root_cfg(), data)
            print(new_data)


def v2_transform_remote_format(data: dict) -> List[dict]:
    """把 {addr: patch_rules} 格式转换为 [{addr: addr, patch_rules: patch_rules}] 格式"""
    return [{"addr": addr, "patch_rules": patch_rules} for addr, patch_rules in data.items()]


def v2_transform_cache_format(data: dict) -> List[dict]:
    """把 {addr: patch_rules} 格式转换为 [{addr: addr, patch_rules: patch_rules}] 格式"""
    return [{"addr": addr, "patches": patch_rules} for addr, patch_rules in data.items()]


def v2_migrate_remote_data():
    # 原始数据 dict
    data = RemoteSw().load()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            mode_dict: dict = RemoteSw().get_(sw, mode)
            if RemoteSwKey.CHANNELS not in mode_dict:
                continue
            channels_dict = mode_dict[RemoteSwKey.CHANNELS]
            for channel in channels_dict:
                feature_ver_dict = channels_dict[channel][RemoteSwKey.FEATURES_ADAPT]
                for ver in feature_ver_dict:
                    ver_dict = feature_ver_dict[ver]
                    if not isinstance(ver_dict, dict):
                        continue
                    print(ver_dict)
                    new_ver_dict = v2_transform_remote_format(ver_dict)
                    data = RemoteSw().load()
                    DictUtils.set_nested_values(
                        data, None, sw, mode, RemoteSwKey.CHANNELS,
                        channel, RemoteSwKey.FEATURES_ADAPT, **{ver: new_ver_dict})
                    JsonUtils.save_json(RemoteSw().get_file_path_from_root_cfg(), data)


def v2_migrate_cache_data():
    # 原始数据 dict
    data = SwCache().get_()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            mode_dict: dict = SwCache().get_(sw, mode)
            if not isinstance(mode_dict, dict) or RemoteSwKey.CHANNELS not in mode_dict:
                continue
            channels_dict = mode_dict[RemoteSwKey.CHANNELS]
            for channel in channels_dict:
                feature_ver_dict = channels_dict[channel][RemoteSwKey.PRECISES]
                for ver in feature_ver_dict:
                    ver_dict = feature_ver_dict[ver]
                    if not isinstance(ver_dict, dict):
                        continue
                    print(ver_dict)
                    new_ver_dict = v2_transform_cache_format(ver_dict)
                    data = SwCache().get_()
                    DictUtils.set_nested_values(
                        data, None, sw, mode, RemoteSwKey.CHANNELS,
                        channel, RemoteSwKey.PRECISES, **{ver: new_ver_dict})
                    SwCache().save(data)


if __name__ == "__main__":
    pass
    # v2_migrate_remote_data()
    # migrate_remote_data()
    v2_migrate_cache_data()
