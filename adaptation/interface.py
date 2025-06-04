from abc import ABC, abstractmethod


class SwInterface(ABC):
    @abstractmethod
    def create_multiple_lnk(self, pid):
        """获取对应账号的密钥"""
        pass
