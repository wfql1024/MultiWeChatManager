import queue
from enum import Enum


class QueueWithUpdate(queue.Queue):
    """
    带有更新功能的队列
    """
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback  # 更新状态栏的回调函数

    def put(self, item, block=True, timeout=None):
        """重写入队方法，入队时立即更新状态栏"""
        super().put(item, block, timeout)
        self.update_callback()  # 入队后，立即触发更新状态栏

    def get(self, block=True, timeout=None):
        """重写出队方法，返回消息"""
        try:
            item = super().get(block, timeout)
            return item
        except queue.Empty:
            return None


class Condition:
    class ConditionType(Enum):
        EQUAL = "equal"
        NOT_EQUAL = "not_equal"
        OR_INT_SCOPE = "or_scope"
        AND_INT_SCOPE = "and_scope"
        OR = "or"
        AND = "and"

    def __init__(self, value, condition_type: ConditionType, condition):
        self.condition = condition
        self.condition_type = condition_type
        self.value = value

    def check(self):
        if self.condition_type == Condition.ConditionType.EQUAL:
            return self.value == self.condition

        elif self.condition_type == Condition.ConditionType.NOT_EQUAL:
            return self.value != self.condition

        elif (self.condition_type == Condition.ConditionType.OR_INT_SCOPE
              or self.condition_type == Condition.ConditionType.AND_INT_SCOPE):
            # self.condition 必须是由二元组（Op[int], Op[int]）组成的列表
            if not isinstance(self.condition, list):
                return False
            if not isinstance(self.value, int):
                return False
            return self.check_int_scope()

        elif (self.condition_type == Condition.ConditionType.OR
              or self.condition_type == Condition.ConditionType.AND):
            # self.condition 必须是由 Condition 组成的列表
            if not isinstance(self.condition, list):
                return False

    def check_int_scope(self):
        # 或区间检验：若 value 落在任意一个区间内，则返回 True
        if self.condition_type == Condition.ConditionType.OR_INT_SCOPE:
            for condition in self.condition:
                if not isinstance(condition, tuple) or len(condition) != 2:
                    # 非法形式跳过
                    continue
                left, right = condition
                if (left is None or isinstance(left, int)) and (right is None or isinstance(right, int)):
                    if (left is None or self.value >= left) and (right is None or self.value <= right):
                        return True
            return False
        # 与区间检验：若 value 落在所有区间内，则返回 True
        elif self.condition_type == Condition.ConditionType.AND_INT_SCOPE:
            for condition in self.condition:
                if not isinstance(condition, tuple) or len(condition) != 2:
                    # 非法形式跳过
                    continue
                left, right = condition
                if (left is None or isinstance(left, int)) and (right is None or isinstance(right, int)):
                    if not (left is None or self.value >= left) or not (right is None or self.value <= right):
                        return False
            return True


class Conditions:
    class LogicCalcType(Enum):
        OR = "or"
        AND = "and"

    def __init__(self, calc_type, *conditions):
        self.conditions = conditions
        self.calc_type = calc_type

    def check(self):
        if self.calc_type == Conditions.LogicCalcType.OR:
            for condition in self.conditions:
                if not condition.check():
                    return True
            return False
        elif self.calc_type == Conditions.LogicCalcType.AND:
            for condition in self.conditions:
                if not condition.check():
                    return False
            return True
