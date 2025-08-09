import base64
import colorsys
import re
from pathlib import Path
from typing import Any, Tuple, Union, Optional

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import unpad, pad

from utils.logger_utils import mylogger as logger


class CryptoUtils:
    @staticmethod
    def get_device_fingerprint():
        # 示例：获取 MAC 地址 + 主板序列号等信息
        import uuid
        mac = uuid.getnode()
        return f"{mac}"  # 可拼接更多字段

    @staticmethod
    def _derive_key(device_info: str, salt: bytes) -> bytes:
        # 通过 PBKDF2 从设备信息派生 AES 密钥
        return PBKDF2(device_info, salt, dkLen=32, count=100000)

    @classmethod
    def encrypt_data(cls, data: str, device_info: str) -> dict:
        """将str加密为dict, 和decrypt_data配套使用"""
        salt = get_random_bytes(16)
        key = cls._derive_key(device_info, salt)
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode('utf-8'))
        return {
            'salt': base64.b64encode(salt).decode(),
            'nonce': base64.b64encode(cipher.nonce).decode(),
            'tag': base64.b64encode(tag).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode()
        }

    @classmethod
    def decrypt_data(cls, enc_dict: dict, device_info: str) -> str:
        """将dict解密为str, 和encrypt_data配套使用"""
        salt = base64.b64decode(enc_dict['salt'])
        key = cls._derive_key(device_info, salt)
        cipher = AES.new(key, AES.MODE_GCM, nonce=base64.b64decode(enc_dict['nonce']))
        data = cipher.decrypt_and_verify(
            base64.b64decode(enc_dict['ciphertext']),
            base64.b64decode(enc_dict['tag'])
        )
        return data.decode('utf-8')

    @classmethod
    def decrypt_response(cls, response_text):
        """将远端加密的response解密, 和encrypt_and_append_key配套使用"""
        # 分割加密数据和密钥
        encrypted_data, key = response_text.rsplit(' ', 1)

        # 解码 Base64 数据
        encrypted_data = base64.b64decode(encrypted_data)
        aes_key = key.ljust(16)[:16].encode()  # 确保密钥长度

        # 提取 iv 和密文
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]

        # 解密
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

        return plaintext.decode()

    @classmethod
    def encrypt_and_append_key(cls, json_data, key) -> str:
        """将json文件加密并追加key, 适合加密远端配置数据, 和decrypt_response配套使用"""
        # 确保密钥长度为16、24或32字节
        aes_key = key.ljust(16)[:16].encode()  # 调整密钥长度
        cipher = AES.new(aes_key, AES.MODE_CBC)
        iv = cipher.iv
        # 加密数据
        ciphertext = cipher.encrypt(pad(json_data.encode(), AES.block_size))
        # 将加密结果和 iv 转为 Base64 字符串
        encrypted_data = base64.b64encode(iv + ciphertext).decode()
        return encrypted_data + " " + key


class StringUtils:
    @staticmethod
    def extract_longest_substring(wildcard: str) -> str:
        """从通配符中提取最长的子字符串。"""
        # 使用 * 和 ? 作为分隔符切分
        parts = re.split(r'[*?]', wildcard)
        # 过滤空串，返回最长的那一段
        return max((part for part in parts if part), key=len, default='')

    @staticmethod
    def wildcard_to_regex(wildcard_pattern: str) -> str:
        """
        将通配符字符串转换为正则表达式：
        ? → 任意单个字符（.）
        * → 任意长度字符（.*）
        其他字符会进行正则转义
        """
        regex = ''
        for char in wildcard_pattern:
            if char == '?':
                regex += '.'
            elif char == '*':
                regex += '.*'
            else:
                regex += re.escape(char)
        return '^' + regex + '$'  # 确保全匹配

    @staticmethod
    def clean_texts(*texts) -> Union[Tuple, str, Any]:
        """
        清理传入的文本，确保其兼容 Tkinter 显示。
        对每个文本中的字符进行检查，替换所有 Unicode 码点 > U+FFFF 的字符为 '_'

        Args:
            *texts: 一个或多个需要清理的字符串。

        Returns:
            tuple: 清理后的字符串。如果只传入一个字符串，则返回单个字符串。
        """

        def clean_text(text):
            if not isinstance(text, str):
                return text  # 非字符串类型直接返回
            cleaned_text = []
            for index, char in enumerate(text):
                code_point = ord(char)
                if code_point > 0xFFFF:
                    logger.warning(f"警告: 在位置 {index} 发现不支持的字符 (U+{code_point:04X})，已替换为 '_'")
                    cleaned_text.append('_')
                else:
                    cleaned_text.append(char)
            return ''.join(cleaned_text)

        # 对每个文本进行清理
        cleaned_texts = tuple(clean_text(text) for text in texts)

        # 如果只传入一个文本，则返回单个字符串而非元组
        return cleaned_texts if len(cleaned_texts) > 1 else cleaned_texts[0]

    @staticmethod
    def balanced_wrap_text(text, max_width=10) -> str:
        """
        将文本按指定宽度尽量平分两行处理，超过 max_width 的部分尽量让上行更长。
        :param text: 要处理的文本
        :param max_width: 每行最大字符数
        :return: 处理后的文本
        """
        # 如果文本长度小于等于 max_width，直接返回文本
        if len(text) <= max_width:
            return text

        # 计算平分点，使得上行尽量更长
        middle = (len(text) + 1) // 2

        # 将文本平分为两行
        return text[:middle] + "\n" + text[middle:]

    @staticmethod
    def try_convert_to_float(value):
        try:
            return float(value)
        except ValueError:
            return value


class ColorUtils:
    @staticmethod
    def rgb_to_hex(rgb):
        """
        将RGB颜色转换为十六进制颜色代码
        :param rgb: 一个包含RGB值的元组，例如(255, 0, 0)
        :return: 十六进制颜色代码，例如'#FF0000'
        :raises ValueError: 当RGB值不合法时抛出异常
        """
        # 验证RGB格式
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
            raise ValueError("RGB值必须是包含3个元素的列表或元组")

        for value in rgb:
            if not isinstance(value, int) or value < 0 or value > 255:
                raise ValueError("RGB值必须是0-255之间的整数")

        return '#{:02X}{:02X}{:02X}'.format(*rgb)

    @staticmethod
    def hex_to_rgb(hex_color):
        """
        将十六进制颜色代码转换为RGB颜色
        :param hex_color: 十六进制颜色代码，例如'#FF0000'或'FF0000'
        :return: 一个包含RGB值的元组，例如(255, 0, 0)
        :raises ValueError: 当十六进制颜色代码格式不正确时抛出异常
        """
        # 验证十六进制格式
        hex_color = hex_color.lstrip('#')
        if not len(hex_color) == 6:
            raise ValueError("十六进制颜色代码必须是6位")
        if not all(c in '0123456789ABCDEFabcdef' for c in hex_color):
            raise ValueError("十六进制颜色代码只能包含0-9和A-F字符")

        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def fade_color(color, white_ratio=0.5):
        """
        颜色淡化工具方法,支持RGB元组或十六进制颜色值.输入负数时会变成加深.
        :param color: RGB元组(如(255,0,0))或十六进制颜色值(如'#FF0000')
        :param white_ratio: 白色混合比例（0~1）
        :return: 与输入格式相同的淡化后的颜色值
        :raises ValueError: 当颜色格式不正确或white_ratio不在0-1之间时抛出异常
        """
        # 验证white_ratio
        if not isinstance(white_ratio, (int, float)) or white_ratio < -1 or white_ratio > 1:
            raise ValueError("white_ratio必须是-1到1之间的数值")

        # 判断输入格式并统一转为RGB
        is_hex = isinstance(color, str)
        if is_hex:
            rgb = ColorUtils.hex_to_rgb(color)
        elif isinstance(color, (list, tuple)) and len(color) == 3:
            rgb = color
            # 验证RGB值
            for value in rgb:
                if not isinstance(value, int) or value < 0 or value > 255:
                    raise ValueError("RGB值必须是0-255之间的整数")
        else:
            raise ValueError("颜色值必须是RGB元组或十六进制字符串")

        if white_ratio >= 0:
            # 比例为正值,与白色混合
            result_rgb = tuple(int(v * (1 - white_ratio) + 255 * white_ratio) for v in rgb)
        else:
            # 比例为负值,与黑色混合
            black_ratio = -white_ratio
            result_rgb = tuple(int(v * (1 - black_ratio)) for v in rgb)

        # 返回对应格式
        if is_hex:
            return ColorUtils.rgb_to_hex(result_rgb)
        return result_rgb

    @staticmethod
    def brighten_color(color):
        """
        提亮颜色，更鲜艳（通过增加亮度和/或饱和度）
        :param color: RGB元组或十六进制字符串
        # :param brighten_ratio: 提亮比例 0~1
        """
        # if not isinstance(brighten_ratio, (int, float)) or brighten_ratio < 0 or brighten_ratio > 1:
        #     raise ValueError("brighten_ratio必须是0-1之间的数值")

        is_hex = isinstance(color, str)
        if is_hex:
            rgb = ColorUtils.hex_to_rgb(color)
        else:
            rgb = color

        # RGB -> HLS
        r, g, b = [v / 255 for v in rgb]
        h, l, s = colorsys.rgb_to_hls(r, g, b)

        # 提亮：增加亮度
        l = 0.5
        # 或者同时增加饱和度:
        s = 0.75

        # HLS -> RGB
        r_new, g_new, b_new = colorsys.hls_to_rgb(h, l, s)
        result_rgb = (int(r_new * 255), int(g_new * 255), int(b_new * 255))

        if is_hex:
            return ColorUtils.rgb_to_hex(result_rgb)
        return result_rgb


class VersionUtils:
    @staticmethod
    def find_compatible_version(current_version: str, version_list: list) -> Optional[str]:
        """
        在版本列表中查找兼容版本（纯版本号降序匹配）

        参数:
            current_version: 当前版本号 (格式 "x.x.x.x")
            version_list: 可用的版本号列表 (元素可能是 "x.x", "x.x.x" 或 "x.x.x.x")

        返回:
            匹配到的最大兼容版本号，如果没有则返回 None
        """

        def normalize_version(vers: str) -> tuple:
            """将版本号转换为四位元组，不足补零"""
            parts = list(map(int, vers.split('.')))
            while len(parts) < 4:
                parts.append(0)
            return tuple(parts[:4])  # 确保只有四位

        current = normalize_version(current_version)

        # 过滤出所有<=当前版本的候选，并标准化
        candidates = []
        for ver in version_list:
            norm_ver = normalize_version(ver)
            if norm_ver <= current:
                candidates.append((norm_ver, ver))

        if not candidates:
            return None

        candidates.sort(reverse=True, key=lambda x: x[0])

        return candidates[0][1]


class PathUtils:
    @staticmethod
    def is_valid_path(path) -> bool:
        if not path or str(path).strip().lower() == "none":
            return False
        try:
            formatted_path = Path(path)
            return formatted_path.exists()
        except Exception as e:
            print(e)
            return False
