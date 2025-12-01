from concurrent.futures import TimeoutError, ThreadPoolExecutor
from concurrent.futures.thread import BrokenThreadPool
from typing import Callable


class GlobalMembers:
    _instance = None
    _root_class = None
    _root = None
    _thread_pool = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ---------------- root_class ----------------
    @property
    def root_class(self):
        return self._root_class

    @root_class.setter
    def root_class(self, value):
        self._root_class = value

    def get_root_class(self):
        return self._root_class

    def set_root_class(self, value):
        self._root_class = value

    # ---------------- root ----------------
    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, value):
        self._root = value

    def get_root(self):
        return self._root

    def set_root(self, value):
        self._root = value

    # ---------------- 进程池 ----------------
    @property
    def thread_pool(self):
        if self._thread_pool is None or self._is_broken(self._thread_pool):
            print("[GlobalMembers] 新建进程池...")
            self._thread_pool = ThreadPoolExecutor()
        return self._thread_pool

    @thread_pool.setter
    def thread_pool(self, pool):
        self._thread_pool = pool

    def get_thread_pool(self):
        return self.thread_pool  # 自动检查可用性

    def set_thread_pool(self, pool):
        self._thread_pool = pool

    @staticmethod
    def _is_broken(pool: ThreadPoolExecutor):
        try:
            fut = pool.submit(lambda: 1)
            fut.result(timeout=1)
            return False
        except (BrokenThreadPool, TimeoutError, Exception):
            print("[GlobalMembers] 检测到进程池损坏")
            return True

    # ---------------- 装饰器 ----------------
    @classmethod
    def run_in_process(cls, func):
        """
        装饰器：将纯函数提交到全局进程池执行。
        返回值会直接解包 Future.result()。
        """

        def wrapper(*args, **kwargs):
            future = cls().get_thread_pool().submit(func, *args, **kwargs)
            return future.result()

        return wrapper

    # ---------------- 回调方法 ----------------
    def wait_res_to_run(self, callback, func, *args, **kwargs):
        """
        将 func 提交到全局进程池执行，func 完成后执行 callback。
        callback 接收 func 的结果作为唯一参数。
        """
        future = self.get_thread_pool().submit(func, *args, **kwargs)

        def _on_done(fut):
            try:
                result = fut.result()
                if isinstance(callback, Callable):
                    callback(*result)
            except Exception as e:
                print(f"[GlobalMembers] 回调执行异常: {e}")

        future.add_done_callback(_on_done)
        return future
