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
    channels = coexist_dict.get("channel", {})
    top_feature = coexist_dict.get("feature", {})
    top_precise = coexist_dict.get("precise", {})

    for channel_name, channel_info in channels.items():
        # feature
        channel_feature = {}
        for version, versions_info in top_feature.items():
            if channel_name in versions_info:
                channel_feature[version] = versions_info[channel_name]
        if channel_feature:
            channel_info["feature"] = channel_feature

        # precise
        channel_precise = {}
        for version, versions_info in top_precise.items():
            if channel_name in versions_info:
                channel_precise[version] = versions_info[channel_name]
        if channel_precise:
            channel_info["precise"] = channel_precise

    return coexist_dict


if __name__ == "__main__":
    # 原始数据 dict
    original_data = {
        "coexist": {
            "channel": {
                "default": {
                    "label": "默认",
                    "introduce": "对host文件,dll文件名,配置文件,互斥体等进行克隆并取别名,实现多套共存程序及配置.共存标号从1开始.",
                    "author": [
                        "afaa1991"
                    ],
                    "exe_wildcard": "Weixi?.exe",
                    "sequence": "123456789ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
                    "patch_wildcard": {
                        "%dll_dir%/Weixin.dll": "%dll_dir%/Weixi?.dll"
                    }
                },
                "default2": {
                    "label": "默认2",
                    "introduce": "对host文件,dll文件名,配置文件,互斥体等进行克隆并取别名,实现多套共存程序及配置.共存标号从0开始.",
                    "author": [
                        "afaa1991"
                    ],
                    "exe_wildcard": "Weixin?.exe",
                    "sequence": "0123456789ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
                    "patch_wildcard": {
                        "%dll_dir%/Weixin.dll": "%dll_dir%/Weixin.dl?"
                    }
                }
            },
            "feature": {
                "4.1.0": {
                    "default": {
                        "%dll_dir%/Weixin.dll": {
                            "original": [
                                "68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C",
                                "48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? ?? ?? 6C 5F 63 6F 6E 66 69 67",
                                "58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00",
                                "78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00"
                            ],
                            "modified": [
                                "... !! 2E 78 6D 6C",
                                "... !! 00",
                                "58 00 57 00 65 00 43 00 68 00 61 00 !! ...",
                                "78 00 57 00 65 00 63 00 68 00 61 00 !! ..."
                            ],
                            "meanings": [
                                " h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l",
                                " H  .  g  l  o  b  a  l  _  c  H  .  .  .  N  .  .  H  .  l  _  c  o  n  f  i  ̲g",
                                " X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .",
                                " x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  ."
                            ],
                            "wildcard": "Weixi?.dll"
                        },
                        "%inst_path%": {
                            "original": [
                                "57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00"
                            ],
                            "modified": [
                                "... !! 00 2E 00 64 00 6C 00 6C 00"
                            ],
                            "meanings": [
                                " W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  ."
                            ],
                            "wildcard": "Weixi?.exe"
                        }
                    }
                },
                "4.0.6": {
                    "default": {
                        "%dll_dir%/Weixin.dll": {
                            "original": [
                                "68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C",
                                "48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00",
                                "58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00",
                                "78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00"
                            ],
                            "modified": [
                                "... !! 2E 78 6D 6C",
                                "... !! 00",
                                "58 00 57 00 65 00 43 00 68 00 61 00 !! ...",
                                "78 00 57 00 65 00 63 00 68 00 61 00 !! ..."
                            ],
                            "meanings": [
                                " h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l",
                                " H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .",
                                " X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .",
                                " x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  ."
                            ],
                            "wildcard": "Weixi?.dll"
                        },
                        "%inst_path%": {
                            "original": [
                                "57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00"
                            ],
                            "modified": [
                                "... !! 00 2E 00 64 00 6C 00 6C 00"
                            ],
                            "meanings": [
                                " W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  ."
                            ],
                            "wildcard": "Weixi?.exe"
                        }
                    },
                    "default2": {
                        "%dll_dir%/Weixin.dll": {
                            "original": [
                                "68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C",
                                "48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00",
                                "58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00",
                                "78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00"
                            ],
                            "modified": [
                                "... !!",
                                "... !! 66 C7 05 ?? ?? ?? ?? 67 00",
                                "!! ...",
                                "... !! 00"
                            ],
                            "meanings": [
                                " h  o  s  t  -  r  e  d  i  r  e  c  t  .  x  m  ̲l",
                                " H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .",
                                " ̲X  .  W  .  e  .  C  .  h  .  a  .  t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .",
                                " x  .  W  .  e  .  c  .  h  .  a  .  t  .  W  .  i  .  n  .  d  .  o  .  ̲w  ."
                            ],
                            "wildcard": "Weixin.dl?"
                        },
                        "%inst_path%": {
                            "original": [
                                "57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00"
                            ],
                            "modified": [
                                "... !! 00"
                            ],
                            "meanings": [
                                " W  .  e  .  i  .  x  .  i  .  n  .  .  .  d  .  l  .  ̲l  ."
                            ],
                            "wildcard": "Weixin?.exe"
                        }
                    }
                }
            }
        }
    }

    new_data = migrate_to_channels(original_data)
    print(new_data)

    out = {
        {'coexist': {'channel': {'default': {'label': '默认',
                                             'introduce': '对host文件,dll文件名,配置文件,互斥体等进行克隆并取别名,实现多套共存程序及配置.共存标号从1开始.',
                                             'author': ['afaa1991'], 'exe_wildcard': 'Weixi?.exe',
                                             'sequence': '123456789ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ',
                                             'patch_wildcard': {'%dll_dir%/Weixin.dll': '%dll_dir%/Weixi?.dll'},
                                             'feature': {'4.1.0': {'%dll_dir%/Weixin.dll': {
                                                 'original': ['68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                                              '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? ?? ?? 6C 5F 63 6F 6E 66 69 67',
                                                              '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                                              '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                                                 'modified': ['... !! 2E 78 6D 6C', '... !! 00',
                                                              '58 00 57 00 65 00 43 00 68 00 61 00 !! ...',
                                                              '78 00 57 00 65 00 63 00 68 00 61 00 !! ...'],
                                                 'meanings': [' h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l',
                                                              ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  N  .  .  H  .  l  _  c  o  n  f  i  ̲g',
                                                              ' X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                                              ' x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  .'],
                                                 'wildcard': 'Weixi?.dll'}, '%inst_path%': {'original': [
                                                 '57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                                                 'modified': [
                                                     '... !! 00 2E 00 64 00 6C 00 6C 00'],
                                                 'meanings': [
                                                     ' W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  .'],
                                                 'wildcard': 'Weixi?.exe'}},
                                                 '4.0.6': {'%dll_dir%/Weixin.dll': {'original': [
                                                     '68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                                     '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00',
                                                     '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                                     '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                                                     'modified': [
                                                         '... !! 2E 78 6D 6C',
                                                         '... !! 00',
                                                         '58 00 57 00 65 00 43 00 68 00 61 00 !! ...',
                                                         '78 00 57 00 65 00 63 00 68 00 61 00 !! ...'],
                                                     'meanings': [
                                                         ' h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l',
                                                         ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .',
                                                         ' X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                                         ' x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  .'],
                                                     'wildcard': 'Weixi?.dll'},
                                                     '%inst_path%': {'original': [
                                                         '57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                                                         'modified': [
                                                             '... !! 00 2E 00 64 00 6C 00 6C 00'],
                                                         'meanings': [
                                                             ' W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  .'],
                                                         'wildcard': 'Weixi?.exe'}}}},
                                 'default2': {'label': '默认2',
                                              'introduce': '对host文件,dll文件名,配置文件,互斥体等进行克隆并取别名,实现多套共存程序及配置.共存标号从0开始.',
                                              'author': ['afaa1991'], 'exe_wildcard': 'Weixin?.exe',
                                              'sequence': '0123456789ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ',
                                              'patch_wildcard': {'%dll_dir%/Weixin.dll': '%dll_dir%/Weixin.dl?'},
                                              'feature': {'4.0.6': {'%dll_dir%/Weixin.dll': {
                                                  'original': ['68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                                               '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00',
                                                               '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                                               '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                                                  'modified': ['... !!', '... !! 66 C7 05 ?? ?? ?? ?? 67 00', '!! ...',
                                                               '... !! 00'],
                                                  'meanings': [' h  o  s  t  -  r  e  d  i  r  e  c  t  .  x  m  ̲l',
                                                               ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .',
                                                               ' ̲X  .  W  .  e  .  C  .  h  .  a  .  t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                                               ' x  .  W  .  e  .  c  .  h  .  a  .  t  .  W  .  i  .  n  .  d  .  o  .  ̲w  .'],
                                                  'wildcard': 'Weixin.dl?'}, '%inst_path%': {'original': [
                                                  '57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                                                  'modified': ['... !! 00'],
                                                  'meanings': [
                                                      ' W  .  e  .  i  .  x  .  i  .  n  .  .  .  d  .  l  .  ̲l  .'],
                                                  'wildcard': 'Weixin?.exe'}}}}},
                     'feature': {'4.1.0': {'default': {'%dll_dir%/Weixin.dll': {
                         'original': ['68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                      '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? ?? ?? 6C 5F 63 6F 6E 66 69 67',
                                      '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                      '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                         'modified': ['... !! 2E 78 6D 6C', '... !! 00', '58 00 57 00 65 00 43 00 68 00 61 00 !! ...',
                                      '78 00 57 00 65 00 63 00 68 00 61 00 !! ...'],
                         'meanings': [' h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l',
                                      ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  N  .  .  H  .  l  _  c  o  n  f  i  ̲g',
                                      ' X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                      ' x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  .'],
                         'wildcard': 'Weixi?.dll'}, '%inst_path%': {
                         'original': ['57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                         'modified': ['... !! 00 2E 00 64 00 6C 00 6C 00'],
                         'meanings': [' W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  .'],
                         'wildcard': 'Weixi?.exe'}}}, '4.0.6': {'default': {'%dll_dir%/Weixin.dll': {
                         'original': ['68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                      '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00',
                                      '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                      '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                         'modified': ['... !! 2E 78 6D 6C', '... !! 00', '58 00 57 00 65 00 43 00 68 00 61 00 !! ...',
                                      '78 00 57 00 65 00 63 00 68 00 61 00 !! ...'],
                         'meanings': [' h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l',
                                      ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .',
                                      ' X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                      ' x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  .'],
                         'wildcard': 'Weixi?.dll'}, '%inst_path%': {
                         'original': ['57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                         'modified': ['... !! 00 2E 00 64 00 6C 00 6C 00'],
                         'meanings': [' W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  .'],
                         'wildcard': 'Weixi?.exe'}}, 'default2': {'%dll_dir%/Weixin.dll': {
                         'original': ['68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C',
                                      '48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00',
                                      '58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00',
                                      '78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00'],
                         'modified': ['... !!', '... !! 66 C7 05 ?? ?? ?? ?? 67 00', '!! ...', '... !! 00'],
                         'meanings': [' h  o  s  t  -  r  e  d  i  r  e  c  t  .  x  m  ̲l',
                                      ' H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  ̲i  f  .  .  .  A  .  .  g  .',
                                      ' ̲X  .  W  .  e  .  C  .  h  .  a  .  t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  .',
                                      ' x  .  W  .  e  .  c  .  h  .  a  .  t  .  W  .  i  .  n  .  d  .  o  .  ̲w  .'],
                         'wildcard': 'Weixin.dl?'}, '%inst_path%': {
                         'original': ['57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00'],
                         'modified': ['... !! 00'],
                         'meanings': [' W  .  e  .  i  .  x  .  i  .  n  .  .  .  d  .  l  .  ̲l  .'],
                         'wildcard': 'Weixin?.exe'}}}}}}
    }
