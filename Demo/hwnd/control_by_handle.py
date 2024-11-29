# -*- coding:utf-8 -*-
import ctypes
import time

import win32api
import win32con
import win32gui


def get_all_child_handles(parent_handle):
    """
    获取指定父窗口句柄下的所有子窗口句柄。

    :param parent_handle: 父窗口句柄
    :return: 子窗口句柄列表
    """
    child_handles = []

    def enum_child_windows_proc(hwnd, lParam):
        child_handles.append(hwnd)
        return True

    # 定义回调函数类型
    EnumChildWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    enum_proc = EnumChildWindowsProc(enum_child_windows_proc)

    # 调用 EnumChildWindows 来获取所有子窗口
    ctypes.windll.user32.EnumChildWindows(parent_handle, enum_proc, 0)

    return child_handles


def doClick(handle, cx, cy):  # 第四种，可后台
    long_position = win32api.MAKELONG(cx, cy)  # 模拟鼠标指针 传送到指定坐标
    win32api.SendMessage(handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)  # 模拟鼠标按下
    win32api.SendMessage(handle, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)  # 模拟鼠标弹起


handles = set()
flag = False

while True:

    # 从顶层窗口向下搜索主窗口，无法搜索子窗口
    # FindWindow(lpClassName=None, lpWindowName=None)  窗口类名 窗口标题名
    handle = win32gui.FindWindow("WeChatLoginWndForPC", "微信")
    if handle:
        handles.add(handle)
        flag = True
        # # 获取窗口位置
        # left, top, right, bottom = win32gui.GetWindowRect(handle)
        # print(left, top, right, bottom)
        # #获取某个句柄的类名和标题
        # title = win32gui.GetWindowText(handle)
        # clazz_name = win32gui.GetClassName(handle)
        # print(clazz_name)
        # print(title)
        #
        # # 打印句柄
        # # 十进制
        # print(handle)
        # # 十六进制
        # print("%x" % (handle))
        #
        # # 搜索子窗口
        # # 枚举子窗口
        # hwndChildList = []
        # win32gui.EnumChildWindows(handle, lambda hwnd, param: param.append(hwnd), hwndChildList)
        # print(f"hwndChildList: {hwndChildList}")
        #
        # child_handles = get_all_child_handles(handle)
        # print("列表：", child_handles)
        # # for c in child_handles:
        # #     print(f"Child handle: {c}")

    print(f"当前有微信窗口：{handles}")
    for handle in list(handles):
        if win32gui.IsWindow(handle):
            cx = 173
            cy = 353
            doClick(handle, cx, cy)
        else:
            handles.remove(handle)

    time.sleep(2)
    # 检测到出现开始，直接列表再次为空结束
    if flag and len(handles) == 0:
        break

# # FindWindowEx(hwndParent=0, hwndChildAfter=0, lpszClass=None, lpszWindow=None) 父窗口句柄 若不为0，则按照z-index的顺序从hwndChildAfter向后开始搜索子窗体，否则从第一个子窗体开始搜索。 子窗口类名 子窗口标题
# subHandle = win32gui.FindWindowEx(handle, 0, "EDIT", None)
# print(f"subHandle: {subHandle}")
#
# # 获得窗口的菜单句柄
# menuHandle = win32gui.GetMenu(subHandle)
# print(f"menuHandle: {menuHandle}")
# # 获得子菜单或下拉菜单句柄
# # 参数：菜单句柄 子菜单索引号
# subMenuHandle = win32gui.GetSubMenu(menuHandle, 0)
# print(f"subMenuHandle: {subMenuHandle}")
# # 获得菜单项中的的标志符，注意，分隔符是被编入索引的
# # 参数：子菜单句柄 项目索引号
# menuItemHandle = win32gui.GetMenuItemID(subMenuHandle, 0)
# print(f"menuItemHandle: {menuItemHandle}")
# # 发送消息，加入消息队列，无返回
# # 参数：句柄 消息类型 WParam IParam
# win32gui.postMessage(subHandle, win32con.WM_COMMAND, menuItemHandle, 0)


# while True:
#     windowRec = win32gui.GetWindowRect(menuItemHandle)  # 目标子句柄窗口的坐标
#     print(windowRec)
#     tempt = win32api.GetCursorPos()  # 记录鼠标所处位置的坐标
#     print(tempt)
#     x = tempt[0] - windowRec[0]  # 计算相对x坐标
#     y = tempt[1] - windowRec[1]  # 计算相对y坐标
#     print(x, y)
#     time.sleep(0.5)  # 每0.5s输出一次
