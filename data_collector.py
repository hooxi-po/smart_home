import time
from queue import Queue

class DataCollector:
    def __init__(self, device_manager, task_queue):
        self.device_manager = device_manager
        self.task_queue = task_queue

    def collect_temperature(self):
        while True:
            temp = self.device_manager.get_temperature()
            if temp is not None:
                self.task_queue.put({'type': 'temp_update', 'data': temp})
                time.sleep(10)
            else:
                logging.warning("无法获取温度数据，稍后重试")
                time.sleep(30)  # 30s后重试
