from legacy_python.functions import acc_func_impl, sw_func_impl


class FuncTool:
    _SW_FUNC_CACHE = {}

    @staticmethod
    def get_sw_func_impl(base_cls: type, sw: str):
        key = (base_cls.__name__, sw)
        if key in FuncTool._SW_FUNC_CACHE:
            return FuncTool._SW_FUNC_CACHE[key]

        # 生成子类名，例如 base_cls=SwInfoFunc, sw=WeChat => WeChatInfoFunc
        base_name = base_cls.__name__
        if base_name.startswith("Sw"):
            base_suffix = base_name[2:]
        else:
            base_suffix = base_name
        class_name = f"{sw}{base_suffix}"

        try:
            impl_class = getattr(sw_func_impl, class_name)
            if not issubclass(impl_class, base_cls):
                raise TypeError(f"{class_name} 不是 {base_cls.__name__} 的子类")
        except (AttributeError, TypeError):
            impl_class = base_cls

        FuncTool._SW_FUNC_CACHE[key] = impl_class
        return impl_class

    @staticmethod
    def get_sw_acc_func_impl(base_cls: type, sw: str):
        key = (base_cls.__name__, sw)
        if key in FuncTool._SW_FUNC_CACHE:
            return FuncTool._SW_FUNC_CACHE[key]
        class_name = f"{sw}{base_cls.__name__}"
        # Printer().debug(f"class_name: {class_name}")

        try:
            impl_class = getattr(acc_func_impl, class_name)
            if not issubclass(impl_class, base_cls):
                raise TypeError(f"{class_name} 不是 {base_cls.__name__} 的子类")
        except (AttributeError, TypeError):
            impl_class = base_cls

        FuncTool._SW_FUNC_CACHE[key] = impl_class
        return impl_class
