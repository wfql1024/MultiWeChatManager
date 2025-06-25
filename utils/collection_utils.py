from functools import cmp_to_key


def multi_field_cmp(*fields):
    """
    多字段排序
    示例：
        multi_field_cmp((lambda x: x['name'], False), (lambda x: x['age'], True))
    :param fields:  [(getval, reverse), ...]
                    getval: 取值函数
                    reverse: 是否降序
    :return:
    """

    def compare(x, y):
        for getval, reverse in fields:
            xv, yv = getval(x), getval(y)
            if xv != yv:
                if reverse:  # 降序
                    return -1 if xv > yv else 1
                else:  # 升序
                    return -1 if xv < yv else 1
        return 0

    return cmp_to_key(compare)
