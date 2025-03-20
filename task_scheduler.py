from concurrent.futures import ThreadPoolExecutor
import schedule
import time
import signal
import logging

class TaskScheduler:
    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def schedule_task(self, task, interval):
        schedule.every(interval).seconds.do(lambda: self.executor.submit(task))

    def run_scheduler(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    @staticmethod
    def timeout_handler(signum, frame):
        raise TimeoutError("任务执行超时")

    def execute_with_timeout(self, func, timeout=5):
        signal.signal(signal.SIGALRM, self.timeout_handler)
        signal.alarm(timeout)
        try:
            result = func()
            signal.alarm(0)
            return result
        except TimeoutError:
            logging.warning("任务超时，重新调度...")
            self.executor.submit(func)
