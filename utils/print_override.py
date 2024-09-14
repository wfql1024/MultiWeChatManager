import builtins
import functools

from utils import debug_utils  # 你需要确保你的 debug_utils 模块可用

# 保存原始的 print 函数
original_print = builtins.print


# 创建新的 print 函数，自动添加 debug_utils.indent() 前缀
@functools.wraps(original_print)
def new_print(*args, **kwargs):
    indent_prefix = f"{debug_utils.indent()}"
    # indent_prefix = f"{debug_utils.indent()}╭{debug_utils.get_call_stack()}\n{debug_utils.indent()}╰"
    modified_args = (f"{indent_prefix}{arg}" for arg in args)
    original_print(*modified_args, **kwargs)


# 将新的 print 函数覆盖到 builtins.print
builtins.print = new_print


def test():
    print("开启了缩进式print")
