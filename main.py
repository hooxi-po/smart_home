import logging
from device_manager import DeviceManager
from task_scheduler import TaskScheduler
from communication import SocketServer
from data_collector import DataCollector
from web_interface import WebInterface
from queue import Queue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    device_manager = DeviceManager()
    task_scheduler = TaskScheduler()
    task_queue = Queue()

    socket_server = SocketServer(device_manager=device_manager)
    data_collector = DataCollector(device_manager, task_queue)
    web_interface = WebInterface(device_manager)

    def read_temperature():
        temp = device_manager.get_temperature()
        if temp is not None:
            logging.info(f"当前温度：{temp}℃")
        else:
            logging.warning("无法获取温度数据")

    def task_consumer():
        while True:
            task = task_queue.get()
            if task['type'] == 'temp_update':
                logging.info(f"更新温度显示：{task['data']}℃")
            task_queue.task_done()

    task_scheduler.schedule_task(read_temperature, 3600)  # 每小时读取一次温度
    task_scheduler.executor.submit(task_scheduler.run_scheduler)
    task_scheduler.executor.submit(socket_server.start)
    task_scheduler.executor.submit(data_collector.collect_temperature)
    task_scheduler.executor.submit(task_consumer)

    web_interface.run()

if __name__ == '__main__':
    main()
