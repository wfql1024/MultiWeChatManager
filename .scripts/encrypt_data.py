import base64
import shutil

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def encrypt_and_append_key(input_file, output_file, key):
    # 确保密钥长度为16、24或32字节
    aes_key = key.ljust(16)[:16].encode()  # 调整密钥长度
    cipher = AES.new(aes_key, AES.MODE_CBC)
    iv = cipher.iv

    # 读取原始 JSON 文件
    with open(input_file, 'r', encoding='utf-8') as f:
        json_data = f.read()

    # 加密数据
    ciphertext = cipher.encrypt(pad(json_data.encode(), AES.block_size))

    # 将加密结果和 iv 转为 Base64 字符串
    encrypted_data = base64.b64encode(iv + ciphertext).decode()

    # 写入加密数据到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(encrypted_data)
        f.write(' ')  # 添加空格
        f.write(key)  # 将密钥追加到最后一行


# 使用方法
my_key = "n3kxCc2yu9FoRQc="
encrypt_and_append_key('origin_remote_setting_v3.json', '../remote_setting', my_key)
print(f"文件已加密并保存为 remote_setting（无后缀名）")
encrypt_and_append_key('origin_remote_setting_v4.json', '../remote_setting_v4', my_key)
print(f"文件已加密并保存为 remote_setting_v4（无后缀名）")
# 复制上级目录中的.old/version_config_v1.json到上上级的version_config.json
shutil.copy('../.old/version_config_v1.json', '../../version_config.json')
print(f"文件已复制项目目录的version_config.json")
# 复制上级目录中的.old/version_adaptation_v2.json到上上级的version_adaptation.json
shutil.copy('../.old/version_adaptation_v2.json', '../../version_adaptation.json')
print(f"文件已复制项目目录的version_adaptation.json")


