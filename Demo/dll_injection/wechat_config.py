class WeChatVersion:
    V3_9_11_25 = "3.9.11.25"
    # 可以在这里添加其他版本


class OffsetConfig:
    def __init__(self, alias, offset, size, data_type):
        self.alias = alias
        self.offset = offset
        self.size = size
        self.data_type = data_type


class OFFSET:
    CONFIGS = {
        WeChatVersion.V3_9_11_25: {
            "NICKNAME": OffsetConfig("昵称", 0x595C3D8, 0, "string"),  # 将 size 设置为 0
            "PHONE_NUMBER": OffsetConfig("手机号", 0x595C318, 11, "ascii_number"),
            "PHONE_TYPE": OffsetConfig("电话类型", 0x595C980, 0, "string")
        }
    }

    @staticmethod
    def get_config(version, key):
        return OFFSET.CONFIGS[version][key]


CURRENT_VERSION = WeChatVersion.V3_9_11_25
