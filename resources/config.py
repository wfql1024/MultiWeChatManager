import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    INI_SECTION = 'default'
    INI_KEY_INSTALL_PATH = 'install_path'
    INI_KEY_DATA_PATH = 'data_path'
    INI_KEY_VER_PATH = 'last_ver_path'
    PROJECT_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJECT_USER_PATH = fr'{PROJECT_PATH}\user_files'
    ACC_DATA_JSON_PATH = fr'{PROJECT_USER_PATH}\account_data.json'
    PATH_INI_PATH = fr'{PROJECT_USER_PATH}\path.ini'
