import queue
import threading
import time
from enum import Enum


class TkThreadWorker:
    """
    Tkinter 线程任务工具类
    本工具过度抽象了其实,直接在要线程运行的方法里使用root.after()即可,无需使用本工具
    本工具主要是为了实现主线程与子线程的通信, 主线程可以通过 main_thread_do_ 方法注册任务, 子线程可以通过 task_queue 队列获取任务,
    但是,after方法本身就是队列轮询, 所以,本工具的意义不大, 留个念想吧
    """

    def __init__(self, root, after_interval=100, max_duration=5):
        """
        :param root: Tkinter 根窗口
        :param after_interval: 主线程轮询队列的间隔(ms)
        :param max_duration: 最大执行时间(秒)
        """
        self._start_time = None
        self.max_duration = max_duration
        self._is_running = False
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
        print(f"注册{method_id}")
        self.main_thread_methods[method_id] = method
        self.task_queue.put(method_id)

    def start_thread(self):
        """启动线程并开始队列轮询"""
        if not callable(self.thread_method):
            return
        self._is_running = True
        self._start_time = time.time()

        threading.Thread(target=self.thread_method, daemon=True).start()
        self._process_queue()

    def _process_queue(self):
        try:
            while True:
                try:
                    method_id = self.task_queue.get_nowait()
                    if method_id in self.main_thread_methods:
                        method = self.main_thread_methods[method_id]
                        if callable(method):
                            method()
                except queue.Empty:
                    break
        finally:
            now = time.time()
            should_stop = not self._is_running
            if self.max_duration is not None:
                should_stop = should_stop or (now - self._start_time >= self.max_duration)

            if not should_stop:
                self.root.after(self.after_interval, self._process_queue)

    def stop_task(self):
        """主动停止队列轮询"""
        print("轮询任务结束咯,不再接收新的主线程任务~")
        self._is_running = False


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
