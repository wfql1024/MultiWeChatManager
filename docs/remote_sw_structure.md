```json
{
    "平台ID": {
        "coexist": {                    --共存
            "alias": "共存",             --别名
            "multi_state": true,        --多状态补丁
            "channels": {               --渠道
                "渠道名": {
                    "alias": "共存",
                    "introduce": "对host文件,dll文件名,配置文件,互斥体等进行克隆并取别名,实现多套共存程序及配置.共存标号从1开始.",
                    "authors": [
                        "afaa1991"
                    ],
                    "exe_wildcard": "Weixi?.exe",           --该共存方案使用的共存程序格式
                    "mutex_wildcard": "XWeCha?_App_Instance_Identity_Mutex_Name",
                    "ordinals": "123456789ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",      --序号串
                    "patch_wildcard": {
                        "%dll_dir%/Weixin.dll": "%dll_dir%/Weixi?.dll"                 --补丁文件对应的共存通配模式
                    },
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.0.6": {
                                            "original": "68 6F 73 74 2D 72 65 64 69 72 65 63 74 2E 78 6D 6C",
                                            "modified": "... !! 2E 78 6D 6C",
                                            "descript": " h  o  s  t  -  r  e  d  i  r  e  c  ̲t  .  x  m  l"
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? ?? ?? 6C 5F 63 6F 6E 66 69 67",
                                            "modified": "... !!",
                                            "descript": " H  .  g  l  o  b  a  l  _  c  H  .  .  .  N  .  .  H  .  l  _  c  o  n  f  i  ̲g"
                                        },
                                        "4.0.6": {
                                            "original": "48 B8 67 6C 6F 62 61 6C 5F 63 48 89 05 ?? ?? ?? ?? C7 05 ?? ?? ?? ?? 6F 6E 66 69 66 C7 05 ?? ?? ?? ?? 67 00",
                                            "modified": "... !! 00",
                                            "descript": " H  .  g  l  o  b  a  l  _  c  H  .  .  .  A  .  .  .  .  .  A  .  .  o  n  f  i  f  .  .  .  A  .  .  ̲g  ."
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.0.6": {
                                            "original": "58 00 57 00 65 00 43 00 68 00 61 00 74 00 5F 00 41 00 70 00 70 00 5F 00 49 00 6E 00 73 00 74 00 61 00 6E 00 63 00 65 00 5F 00 49 00 64 00 65 00 6E 00 74 00 69 00 74 00 79 00 5F 00 4D 00 75 00 74 00 65 00 78 00 5F 00 4E 00 61 00 6D 00 65 00",
                                            "modified": "58 00 57 00 65 00 43 00 68 00 61 00 !! ...",
                                            "descript": " X  .  W  .  e  .  C  .  h  .  a  .  ̲t  .  _  .  A  .  p  .  p  .  _  .  I  .  n  .  s  .  t  .  a  .  n  .  c  .  e  .  _  .  I  .  d  .  e  .  n  .  t  .  i  .  t  .  y  .  _  .  M  .  u  .  t  .  e  .  x  .  _  .  N  .  a  .  m  .  e  ."
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.0.6": {
                                            "original": "78 00 57 00 65 00 63 00 68 00 61 00 74 00 57 00 69 00 6E 00 64 00 6F 00 77 00",
                                            "modified": "78 00 57 00 65 00 63 00 68 00 61 00 !! ...",
                                            "descript": " x  .  W  .  e  .  c  .  h  .  a  .  ̲t  .  W  .  i  .  n  .  d  .  o  .  w  ."
                                        }
                                    }
                                }
                            ],
                            "wildcard": "Weixi?.dll"
                        },
                        {
                            "addr": "%inst_path%",
                            "patch_rules": [
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.0.6": {
                                            "original": "57 00 65 00 69 00 78 00 69 00 6E 00 2E 00 64 00 6C 00 6C 00",
                                            "modified": "... !! 00 2E 00 64 00 6C 00 6C 00",
                                            "descript": " W  .  e  .  i  .  x  .  i  .  ̲n  .  .  .  d  .  l  .  l  ."
                                        }
                                    }
                                }
                            ],
                            "wildcard": "Weixi?.exe"
                        }
                    ]
                }
            }
        },
        "multirun": {
            "alias": "多开",
            "channels": {
                "default": {
                    "alias": "多开",
                    "introduce": "可以在全局进行多开",
                    "authors": [
                        "afaa1991"
                    ],
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "75 1B E8 ?? ?? ?? ?? 84 C0 75 12 E8 ?? ?? ?? ?? 48 89 C1 48 89 F2 E8 ?? ?? ?? ?? 31 FF 89 F8 48 83 C4 28 5F 5E C3 CC CC CC CC",
                                            "modified": "EB ..."
                                        },
                                        "4.0.3": {
                                            "original": "55 56 57 53 48 81 EC C8 01 00 00 48 8D AC 24 80 00 00 00 48 C7 85 40 01 00 00 FE FF FF FF 48 C7 85 A8",
                                            "modified": "C3 ..."
                                        },
                                        "4.0.2": {
                                            "original": "55 41 57 41 56 41 54 56 57 53 48 81 EC ?? ?? ?? ?? 48 8D AC 24 ?? ?? ?? ?? 48 C7 85 ?? ?? ?? ?? FE FF FF FF 48 C7 45 ?? 00 00 00 00",
                                            "modified": "C3 ..."
                                        },
                                        "4.0.1": {
                                            "original": "C7 44 24 ?? FF FF FF FF 31 F6 45 31 C0 41 B9 FF FF FF FF FF 15 ?? ?? ?? ?? 85 C0 75 0F",
                                            "modified": "... EB 0F"
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        },
        "anti-revoke": {
            "alias": "防撤",
            "channels": {
                "silence": {
                    "alias": "静默",
                    "introduce": "不含防撤回提示",
                    "authors": [
                        "zetaloop"
                    ],
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.0.6": {
                                            "original": "0F 84 CF 00 00 00 48 8D 8D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 8D ?? ?? ?? ?? 48 8D 95 ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 8D ?? ?? ?? ?? 48 8D",
                                            "modified": "90 E9 ..."
                                        },
                                        "4.0.3": {
                                            "original": "74 6E 48 8D 8D 28 04 00 00 E8 ?? ?? ?? ?? 48 8B 8D 28 04 00 00 48 8D 95 B0 03 00 00 E8 ?? ?? ?? ?? 48 8B 8D B0 03 00 00 48 8D 95 B0 00 00 00 E8 ?? ?? ?? ?? 48 8D 8D B0 00 00 00 E8 ?? ?? ?? ??",
                                            "modified": "EB ..."
                                        },
                                        "4.0.2.26": {
                                            "original": "74 6E 48 8D 8D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B",
                                            "modified": "EB ..."
                                        },
                                        "4.0.1": {
                                            "original": "75 21 48 B8 72 65 76 6F 6B 65 6D 73 48 89 05 ?? ?? ?? ?? 66 C7 05 ?? ?? ?? ?? 67 00 C6 05 ?? ?? ?? ?? 01 48 8D",
                                            "modified": "EB 21 ..."
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
                "bubble": {
                    "alias": "气泡*",
                    "introduce": "通过气泡进行防撤回提示, 双击可修改",
                    "authors": [
                        "afaa1991"
                    ],
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "jmp_offset",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "55 56 57 53 48 81 EC 68 02 00 00 48 8D AC 24 80 00 00 00 48 C7 85 E0 01 00 00 FE FF FF FF 48 89 D6 48 89 CF 48 8D 5D A0 41 B8 40 02 00 00 48 89 D9 B2 AA E8 ?? ?? ?? ?? 48 89 D9 48 89 F2 E8 ?? ?? ?? ?? 48 89 F9 48 89 DA E8 52 00 00 00 48 8D 4D A0 E8 ?? ?? ?? ?? B0 01 48 81 C4 68 02 00 00",
                                            "modified": "C3 3D 12 27 00 00 0F 84 !! !! !! !! E9 !! !! !! !! 90 90 90 90 90 90 90 ...",
                                            "targets": [
                                                "E8 ?? ?? ?? ?? !48 8B 8D ?? 02 00 00 4C 89 F2 E8 ?? ?? ?? ?? 84 C0 0F 85 ?? ?? ?? ?? 4C 8B BD ?? ?? 00 00 4C 3B BD ?? 03 00 00 0F 84 ?? ?? ?? ?? 4C 89 F9 4C 89 F2",
                                                "00 !48 8B 85 ?? 02 00 00 48 83 F8 10 49 BF CD CC CC CC CC CC CC CC 0F 82 ?? ?? ?? ?? 48 8B 8D ?? ?? 00 00 48 8D 50 01 48 81 FA 00 10 00 00 0F 82 ?? ?? ?? ??"
                                            ]
                                        }
                                    }
                                },
                                {
                                    "type": "jmp_offset",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "44 0F B6 85 ?? 03 00 00 E8 ?? ?? ?? ?? 4C 89 ?? E8 ?? ?? ?? ?? E9 ?? ?? ?? ??",
                                            "modified": "... E9 !! !! !! !!",
                                            "targets": [
                                                "55 !56 57 53 48 81 EC 68 02 00 00 48 8D AC 24 80 00 00 00 48 C7 85 E0 01 00 00 FE FF FF FF 48 89 D6 48 89 CF 48 8D 5D A0 41 B8 40 02 00 00 48 89 D9 B2 AA E8 ?? ?? ?? ?? 48 89 D9 48 89 F2 E8 ?? ?? ?? ?? 48 89 F9 48 89 DA E8 52 00 00 00 48 8D 4D A0 E8 ?? ?? ?? ?? B0 01 48 81 C4 68 02 00 00"
                                            ]
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "CF 00 00 00 48 8D 8D D0 03 00 00 E8 ?? ?? ?? ?? 48 8B 8D D0 03 00 00 48 8D 95 50 03 00 00 E8 ?? ?? ?? ?? 48 8B 8D 50 03 00 00 48 8D 95 B0 00 00 00 E8 ?? ?? ?? ?? 48 8B 8D B0 00 00 00 48 89 F2 E8 ?? ?? ?? ??",
                                            "modified": "... B8 12 27 00 00"
                                        }
                                    }
                                },
                                {
                                    "type": "custom",
                                    "ver_adaptations": {
                                        "4.1.2": {
                                            "original": "E4 B8 8D E6 94 AF E6 8C 81 E7 9A 84 E6 B6 88 E6 81 AF EF BC 8C E5 8F AF E5 9C A8 E6 89 8B E6 9C BA E4 B8 8A E6 9F A5 E7 9C 8B 00",
                                            "modified": "E6 92 A4 E5 9B 9E E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 00 ...",
                                            "encoding": "utf-8",
                                            "tip": "窗口撤回提示消息, 将显示为:[你输入的内容]",
                                            "note": "不支持的消息，可在手机上查看 -> 撤回一条消息",
                                            "suffix_hex": "00"
                                        },
                                        "4.0.3": {
                                            "original": "E6 9A 82 E4 B8 8D E6 94 AF E6 8C 81 E8 AF A5 E5 86 85 E5 AE B9 EF BC 8C E8 AF B7 E5 9C A8 E6 89 8B E6 9C BA E4 B8 8A E6 9F A5 E7 9C 8B 00",
                                            "modified": "E6 92 A4 E5 9B 9E E4 BA 86 E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 00 ...",
                                            "encoding": "utf-8",
                                            "tip": "窗口撤回提示消息, 将显示为:[你输入的内容]",
                                            "note": "暂不支持该内容，请在手机上查看 -> 撤回了一条消息",
                                            "suffix_hex": "00"
                                        }
                                    }
                                },
                                {
                                    "type": "custom",
                                    "ver_adaptations": {
                                        "4.1.2": {
                                            "original": "E4 B8 8D E6 94 AF E6 8C 81 E7 9A 84 E6 B6 88 E6 81 AF 00",
                                            "modified": "E6 92 A4 E5 9B 9E E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 00",
                                            "encoding": "utf-8",
                                            "tip": "列表撤回提示消息",
                                            "note": "不支持的消息 -> 撤回一条消息",
                                            "suffix_hex": "00"
                                        },
                                        "4.0.3": {
                                            "original": "5B E4 B8 8D E6 94 AF E6 8C 81 E7 B1 BB E5 9E 8B E6 B6 88 E6 81 AF 5D 00",
                                            "modified": "5B E6 92 A4 E5 9B 9E E4 BA 86 E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 5D 00",
                                            "encoding": "utf-8",
                                            "tip": "列表撤回提示消息",
                                            "note": "[不支持类型消息] -> [撤回了一条消息]",
                                            "suffix_hex": "00"
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": null,
                                        "4.0.3": {
                                            "original": "E9 68 02 00 00 0F 1F 84 00 00 00 00 00",
                                            "modified": "3D 12 27 00 00 0F 85 62 02 00 00 90 90"
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": null,
                                        "4.0.6": {
                                            "original": "E8 ?? ?? ?? FE 89 C6 48 8B BD B8 00 00 00 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89 F9 FF 10 F0 FF 4F 0C 75 09 48 8B 07 48 89",
                                            "modified": "BE 12 27 00 00 90 90 ..."
                                        },
                                        "4.0.3": {
                                            "original": "E8 ?? ?? ?? ?? 89 C6 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89 F9 FF 10 F0 FF 4F 0C 75 09 48 8B 07 48 89 F9 FF 50 08 48 8B BD B8 00 00 00 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89",
                                            "modified": "8B B5 20 04 00 00 81 C6 12 27 00 00 ..."
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
                "alert": {
                    "alias": "通知",
                    "introduce": "通过系统通知进行防撤回提示",
                    "authors": [
                        "EEEEhex",
                        "afaa1991"
                    ],
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "45 31 C0 ?? ?? ?? ?? FE 48 8B BD 58 04 ?? ?? 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89",
                                            "modified": "48 83 85 D0 02 00 00 01 ..."
                                        },
                                        "4.0.6": {
                                            "original": "45 31 C0 ?? ?? ?? ?? FE 48 8B BD ?? ?? ?? ?? 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89",
                                            "modified": "48 83 85 C0 02 00 00 01 ..."
                                        },
                                        "4.0.5": {
                                            "original": "45 31 C0 E8 ?? ?? ?? FE 48 85 FF 74 1D F0 FF 4F 08 75 17 48 8B 07 48 89 F9 FF 10 F0 FF 4F 0C 75",
                                            "modified": "48 83 85 C0 02 00 00 01 ..."
                                        }
                                    }
                                },
                                {
                                    "type": "simple",
                                    "ver_adaptations": {
                                        "4.1.4": {
                                            "original": "00 ?? 89 ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 89 F0 48 83 C4 30 5E C3 CC CC CC CC CC CC CC CC CC CC CC CC 55 41 57 41 56 56 57 53 48 81",
                                            "modified": "01 ..."
                                        },
                                        "4.0.6": {
                                            "original": "00 ?? ?? ?? FF FF 48 89 F0 48 83 C4 30 5E C3 CC CC CC CC CC 55 41 57 41 56 56 57 53 48 81",
                                            "modified": "01 ..."
                                        },
                                        "4.0.5": {
                                            "original": "00 ?? ?? ?? FF FF 48 89 F0 48 83 C4 30 5E C3 CC CC CC CC CC 55 41 57 41 56 41 54 56 57 53 48 81",
                                            "modified": "01 ..."
                                        }
                                    }
                                },
                                {
                                    "type": "relation",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "children": [
                                                "custom_alert"
                                            ]
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
                "custom_alert": {
                    "alias": "通知*",
                    "introduce": "通过系统通知进行防撤回提示, 双击可改字",
                    "authors": [
                        "afaa1991"
                    ],
                    "features": [
                        {
                            "addr": "%dll_dir%/Weixin.dll",
                            "patch_rules": [
                                {
                                    "type": "jmp_offset",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "48 8D 97 B0 01 00 00 48 83 BF C8 01 00 00 10 72 03 48 8B 12 48 8D 8D 80 00 00 00",
                                            "modified": "48 8D 15 !! !! !! !! 49 83 FD 2F 74 07 48 8D 15 !! !! !! !! 48 8D 8D 80 00 00 00",
                                            "targets": [
                                                "2D 20 E7 82 BA E7 A2 BA E4 BF 9D 20 57 65 43 68 61 74 20 E6 AD A3 E5 B8 B8 E4 BD BF E7 94 A8 EF BC 8C E5 BB BA E8 AD B0 E9 80 80 E5 87 BA 20 57 65 43 68 61 74 20 E4 B8 A6 E9 87 8D E6 96 B0 E5 95 9F E5 8B 95 E9 9B BB E8 85 A6 E5 BE 8C E5 86 8D E4 BD BF E7 94 A8 20 57 65 43 68 61 74 E3 80 82 00",
                                                "2D 20 E5 A6 82 E6 9E 9C E7 95 B0 E5 B8 B8 E4 BB 8D E7 84 B6 E5 87 BA E7 8F BE EF BC 8C E5 8F AF E5 9F B7 E8 A1 8C E7 B3 BB E7 B5 B1 E7 A3 81 E7 A2 9F E5 B7 A5 E5 85 B7 E6 88 96 E7 AC AC E4 B8 89 E6 96 B9 E5 B7 A5 E5 85 B7 E5 B0 8D E7 A3 81 E7 A2 9F E9 80 B2 E8 A1 8C E6 AA A2 E6 9F A5 E3 80 82 00"
                                            ]
                                        }
                                    }
                                },
                                {
                                    "type": "relation",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "parents": [
                                                "alert"
                                            ]
                                        }
                                    }
                                },
                                {
                                    "type": "custom",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "2D 20 E7 82 BA E7 A2 BA E4 BF 9D 20 57 65 43 68 61 74 20 E6 AD A3 E5 B8 B8 E4 BD BF E7 94 A8 EF BC 8C E5 BB BA E8 AD B0 E9 80 80 E5 87 BA 20 57 65 43 68 61 74 20 E4 B8 A6 E9 87 8D E6 96 B0 E5 95 9F E5 8B 95 E9 9B BB E8 85 A6 E5 BE 8C E5 86 8D E4 BD BF E7 94 A8 20 57 65 43 68 61 74 E3 80 82 00",
                                            "modified": "e4 bb a5 e4 b8 8a e6 b6 88 e6 81 af e8 a2 ab e6 92 a4 e5 9b 9e 00 ...",
                                            "encoding": "utf-8",
                                            "tip": "本设备撤回时系统的提示",
                                            "note": "- 為確保 WeChat 正常使用，建議退出 WeChat 並重新啟動電腦後再使用 WeChat。 -> 以上消息被撤回",
                                            "suffix_hex": "00"
                                        }
                                    }
                                },
                                {
                                    "type": "custom",
                                    "ver_adaptations": {
                                        "4.1.0": {
                                            "original": "2D 20 E5 A6 82 E6 9E 9C E7 95 B0 E5 B8 B8 E4 BB 8D E7 84 B6 E5 87 BA E7 8F BE EF BC 8C E5 8F AF E5 9F B7 E8 A1 8C E7 B3 BB E7 B5 B1 E7 A3 81 E7 A2 9F E5 B7 A5 E5 85 B7 E6 88 96 E7 AC AC E4 B8 89 E6 96 B9 E5 B7 A5 E5 85 B7 E5 B0 8D E7 A3 81 E7 A2 9F E9 80 B2 E8 A1 8C E6 AA A2 E6 9F A5 E3 80 82 00",
                                            "modified": "e4 bb a5 e4 b8 8a e6 b6 88 e6 81 af e8 a2 ab e6 92 a4 e5 9b 9e 00 ...",
                                            "encoding": "utf-8",
                                            "tip": "别人或其他设备撤回时系统的提示",
                                            "note": "- 如果異常仍然出現，可執行系統磁碟工具或第三方工具對磁碟進行檢查。 -> 以上消息被撤回",
                                            "suffix_hex": "00"
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        },
        "wnd_class": {
            "login": {
                "matching": {
                    "4.0": [
                        {
                            "ClassNameWildcards": [
                                "mmui::LoginWindow"
                            ]
                        }
                    ]
                },
                "original": {
                    "4.0": {
                        "class_name": "mmui::LoginWindow"
                    }
                }
            },
            "main": {
                "matching": {
                    "4.0.6.30": [
                        {
                            "ClassNameWildcards": [
                                "mmui::MainWindow"
                            ]
                        },
                        {
                            "ClassNameWildcards": [
                                "Qt51514QWindowIcon"
                            ],
                            "FinalSelect": [
                                {
                                    "SizeEquals": 0
                                },
                                {
                                    "SizeExtreme": "max"
                                }
                            ]
                        }
                    ],
                    "4.0": [
                        {
                            "ClassNameWildcards": [
                                "mmui::MainWindow"
                            ]
                        }
                    ]
                },
                "original": {
                    "4.0": {
                        "class_name": "mmui::MainWindow"
                    }
                }
            }
        },
        "alias": "微信4.x",
        "executable": "Weixin.exe",
        "executable_wildcards": [
            "Weixin?.exe",
            "Weixi?.exe"
        ],
        "inst_path_guess_suffix": "Tencent\\Weixin\\Weixin.exe",
        "data_dir_guess_suffix": "Tencent\\Weixin",
        "data_dir_check_suffix": "all_users",
        "dll_dir_check_suffix": "Weixin.dll",
        "patch_dll": "Weixin.dll",
        "mac_reg_sub_key": "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Weixin",
        "user_reg_sub_key": "Software\\Tencent\\Weixin",
        "data_dir_name": "xwechat_files",
        "mutant_handle_infos": [
            {
                "handle_name": "lock.ini",
                "regex": "pid:\\s*(\\d+)\\s+type:\\s*File\\s+([0-9A-Fa-f]+):",
                "type": "file"
            },
            {
                "handle_name": "XWeChat_App_Instance_Identity_Mutex_Name",
                "regex": "pid:\\s*(\\d+).*?(\\w+):\\s*\\\\Sessions",
                "type": "mutant"
            }
        ],
        "cfg_handle_regex_list": [
            {
                "handle_name": "global_config",
                "regex": "pid:\\s*(\\d+)\\s+type:\\s*File\\s+([0-9A-Fa-f]+):",
                "type": "file"
            }
        ],
        "mutant_handle_wildcards": [
            "?WeChat_App_Instance_Identity_Mutex_Name",
            "XWeCha?_App_Instance_Identity_Mutex_Name",
            "lock.ini"
        ],
        "config_handle_wildcards": [
            "global_conf?g",
            "global_confi?"
        ],
        "config_addresses": [
            "%data_dir%/all_users/config/global_config",
            "%data_dir%/all_users/config/global_config.crc"
        ],
        "excluded_dir_list": [      --排除某些目录
            "All Users",
            "Applet",
            "Plugins",
            "WMPF",
            "all_users",
            "Backup",
            "old_backup"
        ],
        "sw_id_trims": {            --相对于其他平台的截取标记
            "WeChat": [
                0,
                0,
                0,
                5
            ]
        }
    }
}