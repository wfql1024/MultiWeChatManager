import json
import os
from Crypto.Util.Padding import pad
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def decrypt_json_file(input_file, output_file, key):
    # 确保密钥长度为 16、24 或 32 字节
    key = key.ljust(16)[:16].encode()

    with open(input_file, 'rb') as f:
        file_data = f.read()

    iv = file_data[:16]
    ciphertext = file_data[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)

    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    with open(output_file, 'wb') as f:
        f.write(plaintext)


def encrypt_json_file(input_file, output_file, key):
    # 确保密钥长度为 16、24 或 32 字节
    key = key.ljust(16)[:16].encode()
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv

    with open(input_file, 'rb') as f:
        plaintext = f.read()

    # 加密并写入文件
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
    with open(output_file, 'wb') as f:
        f.write(iv + ciphertext)


def load_json_data(account_data_file):
    if os.path.exists(account_data_file):
        # print("地址没错")
        with open(account_data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json_data(account_data_file, account_data):
    with open(account_data_file, 'w', encoding='utf-8') as f:
        json_string = json.dumps(account_data, ensure_ascii=False, indent=4)
        f.write(json_string)
