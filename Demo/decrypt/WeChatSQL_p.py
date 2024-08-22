# -*- coding: utf-8 -*-
import ctypes
import hashlib
import hmac
import os

from Crypto.Cipher import AES


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


# def getDbFileName():
#     dbList = []
#     current_dir = os.getcwd()
#     entries = os.listdir(current_dir)
#     # 过滤出文件名，并获取扩展名
#     files_with_extensions = [os.path.splitext(entry) for entry in entries if
#                              os.path.isfile(os.path.join(current_dir, entry))]
#     # 打印所有文件的扩展名
#     for file_name, extension in files_with_extensions:
#         # print(f"文件名: {file_name}, 扩展名: {extension}")
#         if extension == ".db":
#             dbList.append(file_name)
#     return dbList


if __name__ == '__main__':
    pass
