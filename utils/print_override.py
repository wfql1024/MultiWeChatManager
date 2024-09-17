import builtins
import functools

from utils import debug_utils  # 你需要确保你的 debug_utils 模块可用

# 保存原始的 print 函数
original_print = builtins.print


# 创建新的 print 函数，自动添加 debug_utils.indent() 前缀
@functools.wraps(original_print)
def new_print(*args, **kwargs):
    # 灰色的ANSI颜色代码，37代表亮灰色
    gray_color_code = "\033[90m"
    # 重置颜色的代码
    reset_color_code = "\033[0m"

    indent_prefix = f"{debug_utils.indent()}{debug_utils.get_call_stack()}\n{debug_utils.indent()}"
    # 将调用栈部分的文本设置为灰色
    indent_prefix = gray_color_code + indent_prefix + reset_color_code

    modified_args = (
        "\n".join(
            f"{indent_prefix}{line}↓" for line in str(arg).splitlines()
        ).rstrip("↓")
        for arg in args
    )
    original_print(*modified_args, **kwargs)


# 将新的 print 函数覆盖到 builtins.print
builtins.print = new_print


def test():
    print("开启了缩进式print")
