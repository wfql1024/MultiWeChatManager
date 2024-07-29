import sys
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["os", "tkinter", "configparser", "subprocess", "pyautogui", "win32gui", "win32con"],
    "include_files": [
        ("SunnyMultiWxMng.ico", "SunnyMultiWxMng.ico"),
        ("multiWeChat.exe", "multiWeChat.exe"),
        ("path.ini", "path.ini"),
        ("点我创建快捷方式.bat", "点我创建快捷方式.bat")
    ],
    "include_msvcr": True,
}

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="微信多开管理器",
    version="1.1.0",
    description="微信多开管理工具",
    options={"build_exe": build_exe_options},
    executables=[Executable("Main.py", base=base, icon="SunnyMultiWxMng.ico", target_name="微信多开管理器.exe")]
)