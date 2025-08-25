from functions import subfunc_file
from functions.subfunc_file import load_remote_cfg, load_cache_cfg
from public import Config
from public.enums import RemoteCfg
from utils.file_utils import DictUtils, JsonUtils


def migrate_to_channels(data):
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
            channel_info[RemoteCfg.FEATURES] = channel_feature

        # precise
        channel_precise = {}
        for version, versions_info in top_precise.items():
            if channel_name in versions_info:
                channel_precise[version] = versions_info[channel_name]
        if channel_precise:
            channel_info[RemoteCfg.PRECISES] = channel_precise

    return data

def migrate_remote_data():
    # 原始数据 dict
    data = load_remote_cfg()
    for sw in data:
        if sw == "global":
            continue
        for mode in ["coexist", "anti-revoke", "multirun"]:
            original_data = subfunc_file.get_remote_cfg(sw, mode)
            if not isinstance(original_data, dict):
                continue
            new_data = migrate_to_channels(original_data)
            data = load_remote_cfg()
            success = DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            JsonUtils.save_json(Config.REMOTE_SETTING_JSON_PATH, data)
            print(new_data)

def migrate_cache_data():
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
            new_data = migrate_to_channels(original_data)
            subfunc_file.update_cache_cfg(sw, **{mode: new_data})
            # data = load_remote_cfg()
            # success = DictUtils.set_nested_values(data, None, sw, **{mode: new_data})
            # JsonUtils.save_json(Config.REMOTE_SETTING_JSON_PATH, data)
            print(new_data)

if __name__ == "__main__":
    pass
    # migrate_cache_data()
    # migrate_remote_data()


