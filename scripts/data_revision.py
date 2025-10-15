from typing import List

from functions import subfunc_file
from functions.subfunc_file import load_remote_cfg, load_cache_cfg
from public import Config
from public.enums import RemoteCfg
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
            channel_info[RemoteCfg.FEATURES_ADAPT] = channel_feature

        # precise
        channel_precise = {}
        for version, versions_info in top_precise.items():
            if channel_name in versions_info:
                channel_precise[version] = versions_info[channel_name]
        if channel_precise:
            channel_info[RemoteCfg.PRECISES] = channel_precise

    return data


def v1_migrate_remote_data():
    # 原始数据 dict
    data = load_remote_cfg()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            original_data = subfunc_file.get_remote_cfg(sw, mode)
            if not isinstance(original_data, dict):
                continue
            new_data = v1_migrate_to_channels(original_data)
            data = load_remote_cfg()
            DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            JsonUtils.save_json(Config.REMOTE_SETTING_JSON_PATH, data)
            print(new_data)


def v1_migrate_cache_data():
    # 原始数据 dict
    data = load_cache_cfg()
    sws = data.keys()
    for sw in sws:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            original_data = subfunc_file.get_cache_cfg(sw, mode)
            if not isinstance(original_data, dict):
                continue
            new_data = v1_migrate_to_channels(original_data)
            subfunc_file.update_cache_cfg(sw, **{mode: new_data})
            # data = load_remote_cfg()
            # success = DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            # JsonUtils.save_json(Config.REMOTE_SETTING_JSON_PATH, data)
            print(new_data)


def v2_transform_remote_format(data: dict) -> List[dict]:
    """把 {addr: patch_rules} 格式转换为 [{addr: addr, patch_rules: patch_rules}] 格式"""
    return [{"addr": addr, "patch_rules": patch_rules} for addr, patch_rules in data.items()]


def v2_transform_cache_format(data: dict) -> List[dict]:
    """把 {addr: patch_rules} 格式转换为 [{addr: addr, patch_rules: patch_rules}] 格式"""
    return [{"addr": addr, "patches": patch_rules} for addr, patch_rules in data.items()]


def v2_migrate_remote_data():
    # 原始数据 dict
    data = load_remote_cfg()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            mode_dict: dict = subfunc_file.get_remote_cfg(sw, mode)
            if RemoteCfg.CHANNELS not in mode_dict:
                continue
            channels_dict = mode_dict[RemoteCfg.CHANNELS]
            for channel in channels_dict:
                feature_ver_dict = channels_dict[channel][RemoteCfg.FEATURES_ADAPT]
                for ver in feature_ver_dict:
                    ver_dict = feature_ver_dict[ver]
                    if not isinstance(ver_dict, dict):
                        continue
                    print(ver_dict)
                    new_ver_dict = v2_transform_remote_format(ver_dict)
                    data = load_remote_cfg()
                    DictUtils.set_nested_values(
                        data, None, sw, mode, RemoteCfg.CHANNELS,
                        channel, RemoteCfg.FEATURES_ADAPT, **{ver: new_ver_dict})
                    JsonUtils.save_json(Config.REMOTE_SETTING_JSON_PATH, data)


def v2_migrate_cache_data():
    # 原始数据 dict
    data = load_cache_cfg()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            mode_dict: dict = subfunc_file.get_cache_cfg(sw, mode)
            if not isinstance(mode_dict, dict) or RemoteCfg.CHANNELS not in mode_dict:
                continue
            channels_dict = mode_dict[RemoteCfg.CHANNELS]
            for channel in channels_dict:
                feature_ver_dict = channels_dict[channel][RemoteCfg.PRECISES]
                for ver in feature_ver_dict:
                    ver_dict = feature_ver_dict[ver]
                    if not isinstance(ver_dict, dict):
                        continue
                    print(ver_dict)
                    new_ver_dict = v2_transform_cache_format(ver_dict)
                    data = load_cache_cfg()
                    DictUtils.set_nested_values(
                        data, None, sw, mode, RemoteCfg.CHANNELS,
                        channel, RemoteCfg.PRECISES, **{ver: new_ver_dict})
                    JsonUtils.save_json(Config.CACHE_SETTING_JSON_PATH, data)


if __name__ == "__main__":
    pass
    # v2_migrate_remote_data()
    # migrate_remote_data()
    v2_migrate_cache_data()
