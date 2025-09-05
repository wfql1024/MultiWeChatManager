import secrets
import string

from utils.encoding_utils import CryptoUtils


def encrypt_input_and_append_key_to_output(input_file, output_file, key):
    # 读取原始 JSON 文件
    with open(input_file, 'r', encoding='utf-8') as f:
        json_data = f.read()
    # 加密并写入到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(CryptoUtils.encrypt_and_append_key(json_data, key))


# 使用方法
# 生成15个随机字符（大小写字母+数字）
random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(15))
# 组合成最终key（最后补=）
secure_key = random_part + "="
print(secure_key)  # 例如：k8DpLmQwXz5RtN=

# # 复制上级目录中的.old/version_config_v1.json到上上级的version_config.json
# shutil.copy('../.old/original_remote_configs/version_config_v1.json', '../.old/remote_configs/version_config.json')
# print(f"文件已复制项目目录的version_config.json")

# # 复制上级目录中的.old/version_adaptation_v2.json到上上级的version_adaptation.json
# shutil.copy('../.old/original_remote_configs/version_adaptation_v2.json', '../.old/remote_configs/version_adaptation.json')
# print(f"文件已复制项目目录的version_adaptation.json")

# encrypt_input_and_append_key_to_output(
#     '../.old/original_remote_configs/original_remote_setting_v3.json',
#     '../.old/remote_configs/remote_setting', secure_key)
# print(f"文件已加密并保存为 remote_setting")

encrypt_input_and_append_key_to_output(
    'original_remote_setting_v4.json',
    '../remote_setting_v4', secure_key)
print(f"文件已加密并保存为 remote_setting_v4")

# encrypt_input_and_append_key_to_output(
#     '../.old/original_remote_configs/original_remote_setting_v5.json',
#     '../.old/remote_configs/remote_setting_v5', secure_key)
# print(f"文件已加密并保存为 remote_setting_v5")

# encrypt_input_and_append_key_to_output(
#     '../.old/original_remote_configs/original_remote_setting_v6.json',
#     '../remote_configs/remote_setting_v6', secure_key)
# print(f"文件已加密并保存为 remote_setting_v6")

encrypt_input_and_append_key_to_output(
    'original_remote_setting_v7.json',
    '../remote_configs/remote_setting_v7', secure_key)
print(f"文件已加密并保存为 remote_setting_v7")
