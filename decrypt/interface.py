from abc import ABC, abstractmethod

class DecryptInterface(ABC):
    @abstractmethod
    def get_acc_str_key_by_pid(self, pid):
        """获取对应账号的密钥"""
        pass

    @abstractmethod
    def copy_origin_db_to_proj(self, db_path, str_key):
        """通过密钥解密数据库"""
        pass

    @abstractmethod
    def decrypt_db_file_by_str_key(self, pid, db_path, str_key):
        """通过密钥解密数据库"""
        pass

    @abstractmethod
    def get_acc_id_and_alias_from_db(self, cursor, acc):
        """查询数据库获取id和alias"""
        pass

    @abstractmethod
    def get_acc_nickname_from_db(self, cursor, acc):
        """查询数据库获取id和alias"""
        pass

    @abstractmethod
    def get_acc_avatar_from_db(self, cursor, acc):
        """查询数据库获取id和alias"""
        pass


