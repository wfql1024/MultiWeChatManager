import os
import re

import psutil


def get_pid(name):
    """
    获取所有的微信进程
    """
    process_list = psutil.pids()
    pids = []
    for pid in process_list:
        if psutil.Process(pid).name() == name:
            pids.append(pid)
    return pids


def more_open(path):
    pids = get_pid("WeChat.exe")
    for pid in pids:
        # 遍历所有微信的pid 把 Mutex都干掉
        cmd = f"handle -a -u -p {pid}"
        with os.popen(cmd) as f:
            result = f.read()
        search_result = ""
        for i in result.split("\n"):
            if i.strip():
                if i.strip().endswith("_WeChat_App_Instance_Identity_Mutex_Name"):
                    search_result += i
        if not search_result:
            os.startfile(path)
            continue
        re_result = re.findall('(\d+): Mutant', search_result, re.S)
        # 上面这个循环是匹配 Mutex的handle
        if re_result:
            for _id in re_result:
                os.system(f'handle -p {pid} -c {_id} -y')
            os.startfile(path)


path = r"D:\software\Tencent\WeChat\WeChat.exe"
more_open(path)
