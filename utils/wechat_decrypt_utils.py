import binascii
import ctypes
import hashlib
import hmac
import logging
import os
import shutil
import struct
import sys
import time
from pathlib import Path
from resources.config import Config

import psutil
import pymem
import win32api
from Crypto.Cipher import AES
from _ctypes import byref, sizeof, Structure
from win32con import PROCESS_ALL_ACCESS

app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
IV_SIZE = 16
HMAC_SHA1_SIZE = 20
KEY_SIZE = 32
DEFAULT_PAGESIZE = 4096
DEFAULT_ITER = 64000


def check_sqlite_pass(db_file, password):
    db_file = Path(db_file)
    if type(password) == str:  #要是类型是string的，就转bytes
        password = bytes.fromhex(password.replace(' ', ''))
    with open(db_file, 'rb') as (f):
        salt = f.read(16)  #开头的16字节做salt
        first_page_data = f.read(DEFAULT_PAGESIZE - 16)  #从开头第16字节开始到DEFAULT_PAGESIZE整个第一页
    if not len(salt) == 16:
        print(f"{db_file} read failed ")
        return False
    if not len(first_page_data) == DEFAULT_PAGESIZE - 16:
        print(f"{db_file} read failed ")
        return False
    # print(f"{salt=}")
    # print(f"{first_page_data=}")
    key = hashlib.pbkdf2_hmac('sha1', password, salt, DEFAULT_ITER, KEY_SIZE)
    mac_salt = bytes([x ^ 58 for x in salt])
    mac_key = hashlib.pbkdf2_hmac('sha1', key, mac_salt, 2, KEY_SIZE)
    hash_mac = hmac.new(mac_key, digestmod='sha1')
    hash_mac.update(first_page_data[:-32])
    hash_mac.update(bytes(ctypes.c_int(1)))
    if hash_mac.digest() == first_page_data[-32:-12]:
        print(f'{db_file},valid password Success')
        return True
    else:
        print(f'{db_file},valid password Error')
        return False


def get_logger(log_file):
    # 定log输出格式，配置同时输出到标准输出与log文件，返回logger这个对象
    logger = logging.getLogger('mylogger')
    logger.setLevel(logging.DEBUG)
    log_format = logging.Formatter(
        '%(asctime)s - %(filename)s- %(levelname)s - %(message)s')
    log_fh = logging.FileHandler(log_file)
    log_fh.setLevel(logging.DEBUG)
    log_fh.setFormatter(log_format)
    log_ch = logging.StreamHandler()
    log_ch.setLevel(logging.DEBUG)
    log_ch.setFormatter(log_format)
    logger.addHandler(log_fh)
    logger.addHandler(log_ch)
    return logger

def DecrypTo(db_filePath, pwd):
    SQLITE_FILE_HEADER = bytes("SQLite format 3", encoding='ASCII') + bytes(1)  #文件头
    IV_SIZE = 16
    HMAC_SHA1_SIZE = 20
    KEY_SIZE = 32
    DEFAULT_PAGESIZE = 4096  #4048数据 + 16IV + 20 HMAC + 12
    DEFAULT_ITER = 64000
    #yourkey
    password = bytes.fromhex(pwd.replace(' ', ''))

    with open(db_filePath, 'rb') as f:
        blist = f.read()
    print(len(blist))

    salt = blist[:16]  #微信将文件头换成了盐
    key = hashlib.pbkdf2_hmac('sha1', password, salt, DEFAULT_ITER, KEY_SIZE)  #获得Key

    first = blist[16:DEFAULT_PAGESIZE]  #丢掉salt

    # import struct
    mac_salt = bytes([x ^ 0x3a for x in salt])
    mac_key = hashlib.pbkdf2_hmac('sha1', key, mac_salt, 2, KEY_SIZE)

    hash_mac = hmac.new(mac_key, digestmod='sha1')  #用第一页的Hash测试一下
    hash_mac.update(first[:-32])
    hash_mac.update(bytes(ctypes.c_int(1)))
    # hash_mac.update(struct.pack('=I',1))
    if (hash_mac.digest() == first[-32:-12]):
        print('Correct Password')
    else:
        raise RuntimeError('Wrong Password')

    blist = [blist[i:i + DEFAULT_PAGESIZE] for i in range(DEFAULT_PAGESIZE, len(blist), DEFAULT_PAGESIZE)]
    # print(blist)

    if os.path.exists(db_filePath):
        if os.path.isdir(db_filePath):
            pass
        elif os.path.isfile(db_filePath):
            index = db_filePath.rfind("\\")
            orgin = db_filePath[index + 1:]
            db_filePath = db_filePath.replace(orgin, "edit_" + orgin)
    else:
        print(db_filePath, "不存在")

    with open(db_filePath, 'wb') as f:
        f.write(SQLITE_FILE_HEADER)  #写入文件头
        t = AES.new(key, AES.MODE_CBC, first[-48:-32])
        f.write(t.decrypt(first[:-48]))
        f.write(first[-48:])
        for i in blist:
            t = AES.new(key, AES.MODE_CBC, i[-48:-32])
            f.write(t.decrypt(i[:-48]))
            f.write(i[-48:])

app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
log_file = os.path.basename(sys.argv[0]).split('.')[0] + '.log'
cfg_file = os.path.basename(sys.argv[0]).split('.')[0] + '.ini'

mylog = get_logger(log_file)
myDecry = DecrypTo


class MEMORY_BASIC_INFORMATION(Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


#几种内存段可以写入的类型
MEMORY_WRITE_PROTECTIONS = {0x40: "PAGEEXECUTE_READWRITE", 0x80: "PAGE_EXECUTE_WRITECOPY", 0x04: "PAGE_READWRITE",
                            0x08: "PAGE_WRITECOPY"}


def is_writable_region(pid, address):  #判断给定的内存地址是否是可写内存区域，因为可写内存区域，才能指针指到这里写数据
    process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    MBI = MEMORY_BASIC_INFORMATION()
    MBI_pointer = byref(MBI)
    size = sizeof(MBI)
    success = ctypes.windll.kernel32.VirtualQueryEx(
        process_handle,
        ctypes.c_void_p(address),  #64位系统的话，会提示int超范围，这里把指针转换下
        MBI_pointer,
        size)
    ctypes.windll.kernel32.CloseHandle(process_handle)
    if not success:
        return False
    if not success == size:
        return False
    return MBI.Protect in MEMORY_WRITE_PROTECTIONS


def get_current_wechat_key(pid, account):  #遍历微信内存，去暴力找key
    phone_types = [b'android\x00', b'iphone\x00']
    try:
        pm = pymem.Pymem()
        pm.open_process_from_id(pid)
        p = psutil.Process(pid)
        version_info = win32api.GetFileVersionInfo(p.exe(), '\\')
        version = f"{win32api.HIWORD(version_info['FileVersionMS'])}.{win32api.LOWORD(version_info['FileVersionMS'])}.{win32api.HIWORD(version_info['FileVersionLS'])}.{win32api.LOWORD(version_info['FileVersionLS'])}"
        mylog.info(f"wechat version：{version}, wechat pid: {pid}")

        targetdb = [f.path for f in p.open_files() if f.path[-11:] == 'MicroMsg.db']
        print("targetdb", targetdb)

        if len(targetdb) < 1:
            sys.exit(-1)
        else:
            usrDir = Config.PROJECT_USER_PATH
            file_microMsg = usrDir + rf"\{account}_MicroMsg.db"
            shutil.copyfile(targetdb[0], file_microMsg)

        misc_dbs = [f.path for f in p.open_files() if f.path[-7:] == 'Misc.db']
        if len(misc_dbs) < 1:
            mylog.error("没有找到微信当前打开的数据文件，是不是你的微信还没有登录？？")
            sys.exit(-1)

        db_file = misc_dbs[0]  #在wechat.exe打开文件列表里面，找到最后文件名是Misc.db的，用这个做db_file,做校验
        mylog.info(f"db_file:{db_file}")
        min_entrypoint = min([m.EntryPoint for m in pm.list_modules() if
                              m.EntryPoint is not None])  #遍历wechat载入的所有模块（包括它自己），找到所有模块最小的入口地址
        min_base = min([m.lpBaseOfDll for m in pm.list_modules() if
                        m.lpBaseOfDll is not None])  #遍历wechat载入的所有模块（包括它自己），找到所有模块最小的基址
        min_address = min(min_entrypoint, min_base)  #找到wechat最低的内存地址段
        # mylog.info(f"min_address:{min_address:X}")
        phone_addr = None
        for phone_type in phone_types:
            res = pm.pattern_scan_module(phone_type, "wechatwin.dll",
                                         return_multiple=True)  #只在wechatwin.dll这个模块的内存地址段中去寻找电话类型的地址
            if res:
                phone_addr = res[-1]  #地址选搜到的最后一个地址
                break
        if not phone_addr:
            # mylog.error(f"没有找到电话类型之一的关键字{phone_types}")
            sys.exit(-1)
        etime = time.time()
        mylog.info(f"phone_addr:{phone_addr:X}")
        # key_addr=pm.pattern_scan_all(hex_key)
        i = phone_addr  #从找到的电话类型地址，作为基址，从后往前进行查找
        key = None
        str_key = None
        while i > min_address:
            i -= 1
            if phone_addr <= 2 ** 32:  #虽然OS可能是64bit的，但微信是有32bit和64bit的，这里通过前面获得的phone_addr的地址来判断是在32位以内，还是以上，来决定
                key_addr_bytes = pm.read_bytes(i, 4)  # 32位寻址下，地址指针占4个字节，找到存key的地址指针
                key_addr = struct.unpack('<I', key_addr_bytes)[0]
                #mylog.info(f"尝试使用32位寻址去找key,i:{i:X},key_addr:{key_addr:X}")
            else:
                key_addr_bytes = pm.read_bytes(i, 8)  #64位寻址下，地址指针占8个字节，，找到存key的地址指针
                key_addr = struct.unpack('<Q', key_addr_bytes)[0]
                #mylog.info(f"尝试使用64位寻址去找key,i:{i:X},key_addr:{key_addr:X}")
            #mylog.info(f"{i=},{key_addr=}")
            #if key_addr <min_address:   #key_pointer_addr一定是>min_address的，但是key_addr可能是new出来的，不一定，因此这里要这样判断的话，就是个bug，会把正确地址给跳跑了
            # 如果取得的指针在最小的内存内置范围之外，跳过
            #print("取得的指针在最小的内存内置范围之外，跳过")
            #continue
            if not is_writable_region(pm.process_id, key_addr):  #要是这个指针指向的区域不能写，那也跳过
                #print("这个指针指向的区域不能写，那也跳过")
                continue
            key = pm.read_bytes(key_addr, 32)
            if key.count(0x00) >= 5:  #如果一个key里面有5个0x00的话，就很不像是一个sqlite的key，就跳过
                continue
            if check_sqlite_pass(db_file, key):
                str_key = binascii.hexlify(key).decode()
                # mylog.info(f"found key pointer addr:{i:X}, key_addr:{key_addr:X}")
                # mylog.info(f"key:{str_key}")
                break
        if not key:
            # mylog.error("没有找到key")
            sys.exit(-1)
        return str_key
    except Exception as e:
        print("has some exception ", e)
