# 微信多开管理器

微信多开管理器是一个用于管理多个微信账号的桌面应用程序。它的核心功能是保存和调用账号配置，实现快速切换和自动登录选定的微信账号。

## 核心功能

1. **账号配置管理**：
    - 手动创建和保存每个微信账号的配置信息
    - 调用已保存的账号配置，实现自动登录

2. **账号自动登录**：
    - 一键自动登录选定的微信账号

3. **全局多开及多种多开器选择**：
    - 以补丁方式修改dll，使得可以不借助软件实现任意打开新微信登录窗口
    - 非全局多开下，可以选择多开模式。

4. **账号显示管理功能**：
    - 获取微信账号的基本信息，可为每个账号添加自定义备注，方便识别和管理
    - 显示各账号的登录状态
    - 可以手动刷新账号列表

5. **其他功能**：
    - 统计功能
    - 创建快捷多开，使得可以通过不使用软件的方式，而是通过快捷方式直接切换到想要的账号登录
    - 调试器，方便反馈

## 使用说明

1. 首次使用时，会自动获取相关路径，若获取失败，请手动在设置中修改
2. 自动登录功能需要获取微信窗口大小
3. 对尚无配置的账号，请手动登录，登录后在该账号的配置按钮的指引下完成配置
4. 配置之后下次登录便可以使用自动登录
5. 通过账号详情功能可以获取头像昵称微信号等信息
6. 使用全局多开模式可以以极快速度登录多个账号
7. 其余功能敬请自由探索

## 注意事项

- 本程序不含联网功能，不会获取用户隐私信息，隐私安全有保障
- 自动登录功能，会受到微信登录机制的影响：
  - 若三天未登录过电脑端微信，将需要在手机上点击登录（不需要重新配置）
  - 若七天未登录过电脑端微信，将需要重新扫码（不需要重新配置）
  - 若在新设备登录，需要满三天才会在手机上出现自动登录选项

# 项目目录结构
```text
├───Demo  # 做项目时候拿出来单独测试的
│   │   control_by_handle.py
│   │   version_config.py
│   │
│   ├───close_wechat_mutex
│   │       build.bat
│   │       close_wechat_mutex.py
│   │       double_sun.ico
│   │       process_utils.py
│   │       pywinhandle.py
│   │
│   ├───decrypt
│   │   │   mainfuncTion.py
│   │   │   search_wechat_key.py
│   │   │   util.py
│   │   │   WeChatSQL_p.py
│   │   │
│   │   └───__pycache__
│   │           util.cpython-312.pyc
│   │           WeChatSQL_p.cpython-312.pyc
│   │
│   ├───dll_injection
│   │   │   mainTest.py
│   │   │   memory_utils.py
│   │   │   process_utils.py
│   │   │   read_wechat_memory.py
│   │   │   wechat_config.py
│   │   │
│   │   └───__pycache__
│   │           memory_utils.cpython-312.pyc
│   │           process_utils.cpython-312.pyc
│   │           read_wechat_memory.cpython-312.pyc
│   │           wechat_config.cpython-312.pyc
│   │
│   ├───dll_modify
│   │       modify_wechat_dll.py
│   │
│   ├───mutex
│   │       close_mutex_handle.py
│   │       get_wechat_mutex_handle.py
│   │       handle.exe
│   │       main.py
│   │       more_open.py
│   │       wechat_multiple.py
│   │
│   └───__pycache__
│           control_by_handle.cpython-312.pyc
│
├───dist
├───external_res
│       handle.exe
│       path.ini
│       rewards.png
│       SunnyMultiWxMng.ico
│       sy.ini
│       WeChatMultiple_Anhkgg.exe
│       WeChatMultiple_lyie15.exe
│       WeChatMultiple_wfql.exe
│
├───functions
│   │   func_account.py
│   │   func_config.py
│   │   func_detail.py
│   │   func_file.py
│   │   func_login.py
│   │   func_setting.py
│   │   func_wechat_dll.py
│   │   subfunc_file.py
│   │   subfunc_wechat.py
│   │   __init__.py
│   │
│   └───__pycache__
│           func_account.cpython-312.pyc
│           func_config.cpython-312.pyc
│           func_detail.cpython-312.pyc
│           func_file.cpython-312.pyc
│           func_login.cpython-312.pyc
│           func_setting.cpython-312.pyc
│           func_wechat_dll.cpython-312.pyc
│           subfunc_file.cpython-312.pyc
│           subfunc_wechat.cpython-312.pyc
│           __init__.cpython-312.pyc
│
├───resources
│   │   config.py
│   │   constants.py
│   │   strings.py
│   │   __init__.py
│   │
│   └───__pycache__
│           config.cpython-312.pyc
│           constants.cpython-312.pyc
│           strings.cpython-312.pyc
│           __init__.cpython-312.pyc
│
├───ui
│   │   about_ui.py
│   │   debug_ui.py
│   │   detail_ui.py
│   │   loading_ui.py
│   │   main_ui.py
│   │   rewards_ui.py
│   │   setting_ui.py
│   │   statistic_ui.py
│   │   __init__.py
│   │
│   └───__pycache__
│           about_ui.cpython-312.pyc
│           debug_ui.cpython-312.pyc
│           detail_ui.cpython-312.pyc
│           loading_ui.cpython-312.pyc
│           main_ui.cpython-312.pyc
│           rewards_ui.cpython-312.pyc
│           setting_ui.cpython-312.pyc
│           statistic_ui.cpython-312.pyc
│           __init__.cpython-312.pyc
│
├───user_files
│   │   account_data.json
│   │   default.jpg
│   │   setting.ini
│   │   statistics.json
│   │   version_config.json
│   │
│   ├───wxid_5daddxikoccs22
│   │       wxid_5daddxikoccs22.bat
│   │       wxid_5daddxikoccs22.jpg
│   │       wxid_5daddxikoccs22_WeChat.ico
│   │       wxid_5daddxikoccs22_WeChat.png
│   │       wxid_5daddxikoccs22_WeChatMultiple_wfql.ico
│   │       wxid_5daddxikoccs22_WeChatMultiple_wfql.png
│   │
│   ├───wxid_73y712me4tlc22
│   │       wxid_73y712me4tlc22.bat
│   │       wxid_73y712me4tlc22.jpg
│   │       wxid_73y712me4tlc22_WeChat.ico
│   │       wxid_73y712me4tlc22_WeChat.png
│   │       wxid_73y712me4tlc22_WeChatMultiple_wfql.ico
│   │       wxid_73y712me4tlc22_WeChatMultiple_wfql.png
│   │
│   ├───wxid_eeqegbzm9nh822
│   │       wxid_eeqegbzm9nh822.jpg
│   │
│   ├───wxid_g80vnkatetb222
│   │       wxid_g80vnkatetb222.jpg
│   │
│   ├───wxid_h5m0aq1uvr2f22
│   │       wxid_h5m0aq1uvr2f22.bat
│   │       wxid_h5m0aq1uvr2f22.jpg
│   │       wxid_h5m0aq1uvr2f22_WeChat.ico
│   │       wxid_h5m0aq1uvr2f22_WeChat.png
│   │       wxid_h5m0aq1uvr2f22_WeChatMultiple_wfql.ico
│   │       wxid_h5m0aq1uvr2f22_WeChatMultiple_wfql.png
│   │
│   ├───wxid_hvq8w4kcyg8122
│   │       wxid_hvq8w4kcyg8122.bat
│   │       wxid_hvq8w4kcyg8122.jpg
│   │       wxid_hvq8w4kcyg8122_WeChat.ico
│   │       wxid_hvq8w4kcyg8122_WeChat.png
│   │       wxid_hvq8w4kcyg8122_WeChatMultiple_wfql.ico
│   │       wxid_hvq8w4kcyg8122_WeChatMultiple_wfql.png
│   │
│   └───wxid_t2dchu5zw9y022
│           edit_wxid_t2dchu5zw9y022_MicroMsg.db
│           wxid_t2dchu5zw9y022.bat
│           wxid_t2dchu5zw9y022.jpg
│           wxid_t2dchu5zw9y022_WeChat.ico
│           wxid_t2dchu5zw9y022_WeChat.png
│           wxid_t2dchu5zw9y022_WeChatMultiple_wfql.ico
│           wxid_t2dchu5zw9y022_WeChatMultiple_wfql.png
│
├───utils
│   │   debug_utils.py
│   │   file_utils.py
│   │   handle_utils.py
│   │   image_utils.py
│   │   ini_utils.py
│   │   json_utils.py
│   │   logger_utils.py
│   │   memory_utils.py
│   │   print_override.py
│   │   process_utils.py
│   │   pywinhandle.py
│   │   string_utils.py
│   │   wechat_decrypt_utils.py
│   │   wechat_utils.py
│   │   __init__.py
│   │
│   └───__pycache__
│           debug_utils.cpython-312.pyc
│           file_utils.cpython-312.pyc
│           handle_utils.cpython-312.pyc
│           image_utils.cpython-312.pyc
│           ini_utils.cpython-312.pyc
│           json_utils.cpython-312.pyc
│           logger_utils.cpython-312.pyc
│           print_override.cpython-312.pyc
│           process_utils.cpython-312.pyc
│           pywinhandle.cpython-312.pyc
│           string_utils.cpython-312.pyc
│           wechat_decrypt_utils.cpython-312.pyc
│           wechat_utils.cpython-312.pyc
│           __init__.cpython-312.pyc
│
└───__pycache__
        thread_manager.cpython-312.pyc
```


## 支持作者
![我来赏你！](external_res/rewards.png)
