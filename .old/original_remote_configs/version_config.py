class OffsetConfig:
    def __init__(self, alias, pattern):
        self.alias = alias
        self.pattern = pattern


class OFFSET:
    CONFIGS = {
        "3.9.11.25": {
            "STABLE": OffsetConfig("稳定模式", b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'),
            "PATCH": OffsetConfig("补丁模式", b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\xF4\x24\x65\x01')
        },
        "3.9.12.9": {
            "STABLE": OffsetConfig("稳定模式", b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\x24\x65\x65\x01'),
            "PATCH": OffsetConfig("补丁模式", b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\x24\x65\x65\x01')
        },
        "3.9.12.11": {
            "STABLE": OffsetConfig("稳定模式", b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\x84\x5F\x65\x01'),
            "PATCH": OffsetConfig("补丁模式", b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\x84\x5F\x65\x01')
        }
    }

    @staticmethod
    def get_config(version, key):
        return OFFSET.CONFIGS[version][key]


if __name__ == "__main__":
    pattern1 = OFFSET.get_config("3.9.12.11", "STABLE").pattern
    print(pattern1)
