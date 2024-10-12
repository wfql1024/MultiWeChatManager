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

- 本程序除获取新版本外，其余功能不联网，不会获取用户隐私信息，隐私安全有保障
- 自动登录功能，会受到微信登录机制的影响：
  - 若三天未登录过电脑端微信，将需要在手机上点击登录（不需要重新配置）
  - 若七天未登录过电脑端微信，将需要重新扫码（不需要重新配置）
  - 若在新设备登录，需要满三天才会在手机上出现自动登录选项

## 项目目录结构
```markdown
├─📁 Demo---------------------------- # 与项目相关的独立示例代码，可以探索下
│ ├─📁 close_wechat_mutex
│ │ ├─📄 build.bat
│ │ ├─📄 close_wechat_mutex.py
│ │ ├─📄 double_sun.ico
│ │ ├─📄 process_utils.py
│ │ └─📄 pywinhandle.py
│ ├─📁 debug
│ │ └─📄 print_override.py
│ ├─📁 decrypt
│ │ ├─📄 mainfuncTion.py
│ │ ├─📄 search_wechat_key.py
│ │ ├─📄 util.py
│ │ └─📄 WeChatSQL_p.py
│ ├─📁 dll_injection
│ │ ├─📄 mainTest.py
│ │ ├─📄 memory_utils.py
│ │ ├─📄 process_utils.py
│ │ ├─📄 read_wechat_memory.py
│ │ └─📄 wechat_config.py
│ ├─📁 dll_modify
│ │ └─📄 modify_wechat_dll.py
│ ├─📁 mutex
│ │ ├─📄 close_mutex_handle.py
│ │ ├─📄 get_wechat_mutex_handle.py
│ │ ├─📄 handle.exe
│ │ ├─📄 main.py
│ │ ├─📄 more_open.py
│ │ └─📄 wechat_multiple.py
│ ├─📄 control_by_handle.py
│ ├─📄 debug_utils.py
│ └─📄 version_config.py
├─📁 external_res-------------------- # 引用到的外部资源
│ ├─📄 handle.exe
│ ├─📄 path.ini
│ ├─📄 rewards.png
│ ├─📄 SunnyMultiWxMng.ico
│ ├─📄 sy.ini
│ ├─📄 WeChatMultiple_Anhkgg.exe
│ ├─📄 WeChatMultiple_lyie15.exe
│ └─📄 WeChatMultiple_wfql.exe
├─📁 functions----------------------- # 功能层代码，实现项目中的具体功能
│ ├─📄 func_account.py
│ ├─📄 func_config.py
│ ├─📄 func_detail.py
│ ├─📄 func_file.py
│ ├─📄 func_login.py
│ ├─📄 func_setting.py
│ ├─📄 func_wechat_dll.py
│ ├─📄 subfunc_file.py--------------- # subfunc为介于工具类和功能直接实现类的子功能类
│ ├─📄 subfunc_wechat.py
│ └─📄 __init__.py
├─📁 resources----------------------- # 项目代码资源
│ ├─📄 config.py
│ ├─📄 constants.py
│ ├─📄 strings.py
│ └─📄 __init__.py
├─📁 ui------------------------------ # 界面层代码，实现界面创建和更新
│ ├─📄 about_ui.py
│ ├─📄 debug_ui.py
│ ├─📄 detail_ui.py
│ ├─📄 loading_ui.py
│ ├─📄 main_ui.py
│ ├─📄 rewards_ui.py
│ ├─📄 setting_ui.py
│ ├─📄 statistic_ui.py
│ └─📄 __init__.py
├─📁 utils--------------------------- # 工具类代码，可移植到其他项目中使用
│ ├─📄 debug_utils.py
│ ├─📄 file_utils.py
│ ├─📄 handle_utils.py
│ ├─📄 image_utils.py
│ ├─📄 ini_utils.py
│ ├─📄 json_utils.py
│ ├─📄 logger_utils.py
│ ├─📄 memory_utils.py
│ ├─📄 process_utils.py
│ ├─📄 pywinhandle.py
│ ├─📄 string_utils.py
│ ├─📄 wechat_decrypt_utils.py
│ ├─📄 wechat_utils.py
│ └─📄 __init__.py
├─📄 app.manifest
├─📄 build.bat----------------------- # 打包命令，控制台直接使用可以打包项目
├─📄 create_dir_tree.py
├─📄 DirectoryV3.xml
├─📄 main.py------------------------- # 入口，管理员身份及程序参数解析
├─📄 README.md
├─📄 requirements.txt
├─📄 thread_manager.py--------------- # 线程管理器，项目中线程操作统一写在这里
├─📄 tree.txt
├─📄 tree_config.xml
├─📄 version.txt--------------------- # 打包程序的文件版本等信息说明
├─📄 version_adaptation.json--------- # 版本适配表，在这里更新微信新版本的偏移地址
├─📄 version_config.json------------- # 旧的版本适配表，只在发布过的2.3.3.333可以使用，现在代码已经不使用
└─📄 点我创建快捷方式.bat
```

## 支持作者
![我来赏你！](external_res/rewards.png)
