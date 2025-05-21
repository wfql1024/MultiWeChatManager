from typing import Any, Tuple, Union, Optional

from utils.logger_utils import mylogger as logger


class StringUtils:
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
    def lighten_color(color, white_ratio):
        """
        颜色淡化工具方法,支持RGB元组或十六进制颜色值
        :param color: RGB元组(如(255,0,0))或十六进制颜色值(如'#FF0000')
        :param white_ratio: 白色混合比例（0~1）
        :return: 与输入格式相同的淡化后的颜色值
        :raises ValueError: 当颜色格式不正确或white_ratio不在0-1之间时抛出异常
        """
        # 验证white_ratio
        if not isinstance(white_ratio, (int, float)) or white_ratio < 0 or white_ratio > 1:
            raise ValueError("white_ratio必须是0-1之间的数值")

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

        # 与白色混合
        result_rgb = tuple(int(v * (1 - white_ratio) + 255 * white_ratio) for v in rgb)

        # 返回对应格式
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
