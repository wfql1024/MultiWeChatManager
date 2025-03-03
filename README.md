# 微信多开管理器

微信多开管理器是一个用于管理多个微信账号的桌面应用程序。它的核心功能是保存和调用账号配置，实现自动登录选定的微信账号。

## 核心功能
- **win7及以上64位系统可用**
  - win7用户请参考：[win7使用说明](https://github.com/wfql1024/MultiWeChatManager/wiki/How_to_use_in_win7)

- **账号配置管理**：
    - 创建每个账号的配置信息（首次登录账号后会自动保存配置，也可手动配置）
    - 调用已保存的账号配置，实现择号自动登录

- **全局多开及多种多开模式选择**：
    - 以补丁方式修改dll，使得可以不借助软件实现任意打开新微信登录窗口
    - 非全局多开下，可以选择其余的多开模式

- **账号显示、管理功能**：
    - 显示未登录、已登录的账号列表
    - 自动获取账号的昵称、头像等基本信息，可对账号备注方便管理
    - 手动在详情页获取更新的基本信息
    - 可以隐藏账号，可以为账号配置快捷键

- **防撤回功能**：
    - 通过补丁方式实现防撤回功能，可
    - 防撤回功能可在设置中开启或关闭

- **自启动功能**：
    - 可在设置中开启自启动功能，实现开机自启
    - 可以选择要自启的账号，会在每一次启动时检查并登录应该自启的账号

- **其他功能**：
    - 统计功能
    - 创建快捷多开，则可以通过不使用本软件，而是快捷方式直接切换到想要的账号登录
    - 调试器，方便反馈

## 使用说明

- 首次使用时，会自动获取相关路径，若获取失败，请手动在设置中修改
- 尚无配置的账号，需要手动登录，登录后会自动保存配置，有配置方可使用自动登录
- 若在平台上（非本软件）修改了某账号的设置（如修改了快捷键），需要在设置完成后手动重新配置
- 对尚无配置的账号，请手动登录，登录后会自动保存配置，也可以在该账号的配置按钮的指引下完成配置
- 通过账号详情页面的获取按钮可以获取头像昵称微信号等信息（tips：该方式是通过解密数据库获取，数据随用随删不会上传，仍介意者可不使用）
- 全局多开和防撤回功能皆是通过修改dll文件实现的，需要时需退出相应平台的所有账号
- 其余功能敬请自由探索

## 常见问题

- 本程序除`获取新版本`及`版本适配的热更新`外，其余功能不联网，不会获取用户隐私信息，隐私安全有保障
- 自动登录功能，会受到微信登录机制的影响：
    - 若三天未登录过电脑端微信，将需要在手机上点击登录（不需要重新配置）
    - 若七天未登录过电脑端微信，将需要重新扫码（不需要重新配置）
    - 若在新设备登录，需要满三天才会在手机上出现自动登录选项
- PC端登录依赖移动端在线，因此PC多号登录需要手机端也多号同时登录
- 某些账号获取详情可能失败，原因暂不明确，但该功能只是获取头像昵称等信息，不影响其他功能

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
