from enum import Enum
from typing import List


class Condition:
    class ConditionType(Enum):
        EQUAL = "equal"
        OR_SCOPE = "or_scope"
        AND_SCOPE = "and_scope"

    def __init__(self, value, condition_type: ConditionType, condition):
        self.condition = condition
        self.condition_type = condition_type
        self.value = value

    def check(self):
        if self.condition_type == Condition.ConditionType.EQUAL:
            return self.value == self.condition

        elif (self.condition_type == Condition.ConditionType.OR_SCOPE
              or self.condition_type == Condition.ConditionType.AND_SCOPE):
            # self.condition 必须是由二元组（Op[int], Op[int]）组成的列表
            if not isinstance(self.condition, list):
                return False
            if not isinstance(self.value, int):
                return False

            # 或区间检验：若 value 落在任意一个区间内，则返回 True
            if self.condition_type == Condition.ConditionType.OR_SCOPE:
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
            elif self.condition_type == Condition.ConditionType.AND_SCOPE:
                for condition in self.condition:
                    if not isinstance(condition, tuple) or len(condition)!= 2:
                        # 非法形式跳过
                        continue
                    left, right = condition
                    if (left is None or isinstance(left, int)) and (right is None or isinstance(right, int)):
                        if not (left is None or self.value >= left) or not (right is None or self.value <= right):
                            return False
                return True

