import queue
import threading
from enum import Enum


class TkThreadWorker:
    """Tkinter 线程任务工具类"""

    def __init__(self, root, after_interval=100):
        """
        :param root: Tkinter 根窗口
        :param after_interval: 主线程轮询队列的间隔(ms)
        """
        self.root = root
        self.after_interval = after_interval
        self.task_queue = queue.Queue()
        self.thread_method = lambda: print(
            "请将 thread_method 替换为具体的线程方法, 方法体内可使用 main_thread_do_ 方法注册主线程任务")
        self.main_thread_methods = {}  # 存储主线程回调方法 {id: callable}

    def main_thread_do_(self, method_id, method):
        """注册主线程任务
        :param method_id: 任务唯一标识
        :param method: 可调用对象（如 partial 或 lambda）
        """
        self.main_thread_methods[method_id] = method
        self.task_queue.put(method_id)

    def start_thread(self):
        """启动线程并开始队列轮询"""
        if callable(self.thread_method):
            threading.Thread(
                target=self.thread_method,
                daemon=True
            ).start()
            self._process_queue()

    def _process_queue(self):
        """主线程处理队列任务（自动循环）"""
        try:
            while True:
                try:
                    method_id = self.task_queue.get_nowait()
                    if method_id in self.main_thread_methods:
                        method = self.main_thread_methods[method_id]
                        if callable(method):
                            method()  # 执行主线程方法
                except queue.Empty:
                    break
        finally:
            self.root.after(self.after_interval, self._process_queue)


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
