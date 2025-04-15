import os
import xml.etree.ElementTree as ET
from enum import Enum
from pathlib import Path


class CfgNode(str, Enum):
    ROOT_DIR: str = "root_dir"
    IGNORE_DIR_LIST = 'ignore_dir_list'
    IGNORE_FILE_SUFFIX_LIST = 'ignore_file_suffix_list'
    IGNORE_DOT_DIR = 'ignore_dot_dir'
    IGNORE_DOT_FILE = 'ignore_dot_file'
    IGNORE_FILE = 'ignore_file'
    OUTPUT_TYPE = 'output_type'
    TREE_INFO_TIP_XML = 'tree_info_tip_xml'
    LEAST_INDENT_LENGTH = 'least_indent_length'
    CONNECTION_SYMBOL = 'connection_symbol'
    ALWAYS_SHOW_BRIDGE = 'always_show_bridge'
    SIMPLY_SHOW_DIR_LIST = 'simply_show_dir_list'
    COMMENT_PREFIX = 'comment_prefix'
    OUTPUT_DIR = 'output_dir'
    OUTPUT_NAME = 'output_name'


class DirTreeCreator:
    def __init__(self, cfg_path=None):
        self.output_type = None
        self.output_suffix = None
        self.indent_suffix = None
        self.indent_prefix = None
        self.output_path = None
        self.remark_root = None
        self.always_show_bridge = None
        self.connection_symbol = None
        self.least_indent_length_str = None
        self.comment_prefix = None
        self.simply_show_dir_list = None
        self.ignore_file = None
        self.ignore_dir_list = None
        self.ignore_file_suffix_list = None
        self.ignore_dot_file = None
        self.ignore_dot_dir = None
        self.config = None
        self.tree_info_tip_xml = None
        self.base_dir = None
        if cfg_path is not None:
            self.cfg_path = cfg_path
        else:
            sys_dir = Path.cwd()
            self.cfg_path = (Path(sys_dir) / 'dir_tree_config.xml').resolve()

    def get_remark_by_path(self, search_path):
        """
        根据 XML 文件中的路径获取对应的标题。
        :param search_path: 需要查找的路径。
        :return: 该路径对应的标题，如果未找到则返回空字符串。
        """
        if self.remark_root is None:
            return ''

        for tree_element in self.remark_root.findall('tree'):  # 遍历所有 "tree" 节点
            if tree_element.get('path') == search_path:  # 匹配路径
                # print(tree_element.get('title'))
                return tree_element.get('title')  # 返回标题属性

        return ''  # 如果未找到对应的路径，返回空字符串

    @staticmethod
    def load_config(xml_file):
        """
        解析 XML 配置文件，并将其转换为字典。

        :param xml_file: XML 配置文件路径。
        :return: 包含配置项的字典。
        """
        tree = ET.parse(xml_file)  # 解析 XML 文件
        root = tree.getroot()  # 获取根元素
        config = {child.tag: child.text for child in root}  # 提取所有子节点的键值对

        # 处理 root_dir，解析相对路径
        root_dir = config.get(CfgNode.ROOT_DIR, '.')
        config[CfgNode.ROOT_DIR] = str((Path(xml_file).parent / root_dir).resolve()).replace('\\', '/')
        tree_info_tip_xml = config.get(CfgNode.TREE_INFO_TIP_XML, './DirectoryV3.xml')
        config[CfgNode.TREE_INFO_TIP_XML] = str(
            (Path(xml_file).parent / tree_info_tip_xml).resolve()).replace('\\', '/')
        output_dir = config.get(CfgNode.OUTPUT_DIR, '.')
        config[CfgNode.OUTPUT_DIR] = str((Path(xml_file).parent / output_dir).resolve()).replace('\\', '/')
        output_name = config.get(CfgNode.OUTPUT_NAME, '目录树')
        config[CfgNode.OUTPUT_NAME] = output_name
        print(config)

        return config

    def traverse_directory(self, path, level=0, simply_show=False):
        """
        遍历指定目录，并返回格式化的文件和文件夹结构。

        :param simply_show: 简单显示
        :param path: 需要遍历的根目录路径。
        :param level: 递归遍历的层级深度，初始值为 0。
        :return: 目录结构的列表，每个元素包含文件/文件夹名称及注释。
        """

        formatted_dirs = []  # 存放文件夹的列表
        formatted_files = []  # 存放文件的列表

        indent: str = str(self.indent_prefix) * level + str(self.indent_suffix)

        # 解析忽略项的相关参数
        ignore_dot_dir = self.ignore_dot_dir
        ignore_dot_file = self.ignore_dot_file
        ignore_file_suffix_list = self.ignore_file_suffix_list
        ignore_dir_list = self.ignore_dir_list
        ignore_file = self.ignore_file
        simply_show_dir_list = self.simply_show_dir_list
        comment_prefix = self.comment_prefix

        tree_info_tip_xml_path = self.tree_info_tip_xml.replace('\\', '/')

        for item in os.listdir(path):  # 遍历目录中的所有文件和文件夹
            item_path = os.path.join(path, item)  # 生成完整路径

            if os.path.isdir(item_path):  # 处理文件夹
                if ignore_dot_dir and item.startswith('.'):  # 忽略隐藏文件夹
                    continue
                if len(ignore_dir_list) > 0 and any(item == dirname for dirname in ignore_dir_list):  # 忽略特定文件夹
                    continue
                # 判断是否是需要简化的文件夹
                if len(simply_show_dir_list) > 0 and any(item == dirname for dirname in simply_show_dir_list):
                    need_to_simply_show = True
                else:
                    need_to_simply_show = False
                # 但若其位于简化文件夹内，则同样进行简化
                if simply_show is True:
                    need_to_simply_show = True

                comment = ''
                if os.path.exists(tree_info_tip_xml_path):  # 如果 XML 存在，获取文件夹对应的注释
                    comment = self.get_remark_by_path(
                        item_path.replace('\\', '/').replace(str(self.base_dir), ''))
                    if comment:
                        comment = comment_prefix + comment

                formatted_dirs.append((f"{indent}📁 {item}", comment))  # 添加文件夹信息
                formatted_dirs.extend(self.traverse_directory(item_path, level + 1, need_to_simply_show))  # 递归遍历子目录

            else:  # 处理文件
                if ignore_file:  # 是否忽略所有文件
                    continue
                if ignore_dot_file and item.startswith('.'):  # 忽略隐藏文件
                    continue
                if ignore_file_suffix_list and any(
                        item.endswith(suffix) for suffix in ignore_file_suffix_list):  # 忽略特定后缀文件
                    continue

                comment = ''
                line = ''
                if os.path.exists(tree_info_tip_xml_path):  # 如果 XML 存在，获取文件对应的注释
                    comment = self.get_remark_by_path(
                        item_path.replace('\\', '/').replace(str(self.base_dir), ''))
                    if comment:
                        line = comment_prefix + comment

                if simply_show is True:
                    if comment:
                        formatted_files.append((f"{indent}📄 {item}", line))  # 添加文件信息
                    else:
                        continue
                else:
                    formatted_files.append((f"{indent}📄 {item}", line))  # 添加文件信息

        merged_list = formatted_dirs + formatted_files  # 合并文件夹和文件列表
        if len(merged_list) > 0:
            merged_list[-1] = (merged_list[-1][0].replace("├─", "└─"), merged_list[-1][1])  # 调整最后一个元素的连接符
        return merged_list  # 返回格式化的目录结构

    def create_dir_tree(self):
        """
        主函数，加载配置文件，并生成目录树结构。
        """
        self.config: dict = self.load_config(self.cfg_path)  # 加载 XML 配置文件
        config: dict = self.config

        self.least_indent_length_str: str = config.get(CfgNode.LEAST_INDENT_LENGTH, '2')  # 最小缩进长度，默认值为 '2'
        self.connection_symbol: str = config.get(CfgNode.CONNECTION_SYMBOL, '-')  # 连接符号
        self.always_show_bridge: bool = config.get(CfgNode.ALWAYS_SHOW_BRIDGE, 'true').lower() == 'true'  # 是否始终显示连接线
        least_indent_length_str: str = self.least_indent_length_str
        connection_symbol: str = self.connection_symbol
        always_show_bridge: bool = self.always_show_bridge

        self.ignore_dot_dir = config.get(CfgNode.IGNORE_DOT_DIR, 'false').lower() == 'true'
        self.ignore_dot_file = config.get(CfgNode.IGNORE_DOT_FILE, 'false').lower() == 'true'
        self.ignore_file_suffix_list = config.get(CfgNode.IGNORE_FILE_SUFFIX_LIST, '').split(',')
        self.ignore_dir_list = config.get(CfgNode.IGNORE_DIR_LIST, '').split(',')
        self.ignore_file = config.get(CfgNode.IGNORE_FILE, 'false').lower() == 'true'
        self.simply_show_dir_list = config.get(CfgNode.SIMPLY_SHOW_DIR_LIST, '').split(',')
        self.comment_prefix = config.get(CfgNode.COMMENT_PREFIX, ' ')  # 注释前缀

        self.output_type = config.get('output_type', 'text')  # 获取输出格式（默认 'text'）
        output_type = self.output_type

        # 设置目录缩进格式
        if output_type == 'markdown':
            # Markdown 缩进格式
            self.indent_prefix = '\t'
            self.indent_suffix = ' - '
            self.output_suffix = '.md'
        elif output_type == 'text':
            # 文本缩进格式
            self.indent_prefix = '│ '
            self.indent_suffix = '├─'
            self.output_suffix = '.txt'

        # 获取格式化后的目录结构
        self.base_dir = config[CfgNode.ROOT_DIR]  # 直接使用解析后的绝对路径
        print(f"根目录：{self.base_dir}")
        self.tree_info_tip_xml = config[CfgNode.TREE_INFO_TIP_XML]
        print(f"备注路径：{self.tree_info_tip_xml}")
        output_dir = config[CfgNode.OUTPUT_DIR]
        output_name = config[CfgNode.OUTPUT_NAME]
        self.output_path = rf"{output_dir}/{output_name}{self.output_suffix}"
        print(f"输出路径：{self.output_path}")

        try:
            tree = ET.parse(self.tree_info_tip_xml)  # 解析 XML 文件
            self.remark_root = tree.getroot()  # 获取根元素
        except FileNotFoundError:
            print(f"XML 文件不存在：{self.tree_info_tip_xml}。推荐使用TreeInfoTip插件，可以添加目录备注。")
            self.remark_root = None

        formatted_output = self.traverse_directory(self.base_dir)

        # 计算最长行的长度
        max_length = max(len(line[0]) for line in formatted_output) if formatted_output else 0

        # 转换最小缩进长度为整数，防止配置错误
        try:
            least_indent_length = int(least_indent_length_str)
        except ValueError:
            least_indent_length = 2  # 解析失败时使用默认值 2

        dir_tree = []  # 存放最终的目录树结构

        # 处理最终的格式化输出
        if always_show_bridge:
            for i in range(len(formatted_output)):
                dir_tree_lines = formatted_output[i][0] + connection_symbol * (
                        max_length - len(formatted_output[i][0]) + least_indent_length) + formatted_output[i][1]
                dir_tree.append(dir_tree_lines)
        else:
            for i in range(len(formatted_output)):
                if len(formatted_output[i][1]) == 0:
                    dir_tree_lines = formatted_output[i][0]
                else:
                    dir_tree_lines = formatted_output[i][0] + connection_symbol * (
                            max_length - len(formatted_output[i][0]) + least_indent_length) + formatted_output[i][1]
                dir_tree.append(dir_tree_lines)

        # 将目录树写入文件
        with open(self.output_path, 'w', encoding='utf-8') as f:
            print('\n'.join(dir_tree))
            f.write('\n'.join(dir_tree))


if __name__ == "__main__":
    DirTreeCreator().create_dir_tree()  # 无参构造，使用的配置文件在脚本同目录

    # # 有参构造，可以使用绝对路径或相对路径
    # DirTreeCreator(fr'D:\SpaceDev\MyProj\MultiWeChatManager\.scripts\dir_tree_config.xml').create_dir_tree()
