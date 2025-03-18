import socket
import json
from concurrent.futures import ThreadPoolExecutor
import schedule
import time
from queue import Queue
from flask import Flask, jsonify, render_template_string
import signal
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 虚拟设备类
class VirtualDevice:
    def __init__(self, device_path):
        self.device_path = device_path

    def read(self):
        try:
            with open(self.device_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            logging.error(f"设备文件未找到：{self.device_path}")
            return None
        except Exception as e:
            logging.error(f"读取设备文件出错：{e}")
            return None

    def write(self, data):
        try:
            with open(self.device_path, 'w') as f:
                f.write(str(data))
        except FileNotFoundError:
            logging.error(f"设备文件未找到：{self.device_path}")
        except Exception as e:
            logging.error(f"写入设备文件出错：{e}")

# 初始化设备
temp_sensor = VirtualDevice('./virtual_devices/sensor_temp')
light_controller = VirtualDevice('./virtual_devices/light_ctl')

# 线程池
executor = ThreadPoolExecutor(max_workers=5)

# 任务队列
task_queue = Queue()

# 定时任务：读取温度
def read_temperature():
    temp = temp_sensor.read()
    if temp is not None:
        logging.info(f"当前温度：{temp}℃")
    else:
        logging.warning("无法获取温度数据")

schedule.every().hour.do(lambda: executor.submit(read_temperature))

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Socket服务器
def socket_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 8080))
    server.listen(5)
    logging.info("Socket服务器启动，监听端口：8080")
    while True:
        client, addr = server.accept()
        logging.info(f"接收到来自 {addr} 的连接")
        data = client.recv(1024).decode()
        try:
            cmd = json.loads(data)
            if cmd['action'] == 'open_light':
                light_controller.write('ON')
                client.send(json.dumps({'status': 'success'}).encode())
                logging.info("灯光已打开")
            elif cmd['action'] == 'close_light':
                light_controller.write('OFF')
                client.send(json.dumps({'status': 'success'}).encode())
                logging.info("灯光已关闭")
            else:
                client.send(json.dumps({'error': '未知指令'}).encode())
                logging.warning(f"未知指令：{cmd}")
        except Exception as e:
            client.send(json.dumps({'error': str(e)}).encode())
            logging.error(f"处理Socket请求出错：{e}")
        client.close()
        logging.info(f"与 {addr} 的连接已关闭")

# 传感器数据采集
def sensor_producer():
    while True:
        temp = temp_sensor.read()
        if temp is not None:
            task_queue.put({'type': 'temp_update', 'data': temp})
            time.sleep(10)
        else:
            logging.warning("无法获取温度数据，稍后重试")
            time.sleep(30) # 30s后重试

# 任务处理
def task_consumer():
    while True:
        task = task_queue.get()
        if task['type'] == 'temp_update':
            logging.info(f"更新温度显示：{task['data']}℃")
        task_queue.task_done()

# 超时处理
def timeout_handler(signum, frame):
    raise TimeoutError("任务执行超时")

def execute_with_timeout(func, timeout=5):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        result = func()
        signal.alarm(0)
        return result
    except TimeoutError:
        logging.warning("任务超时，重新调度...")
        executor.submit(func)

# Flask应用
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string('''
        <button onclick="controlLight('ON')">开灯</button>
        <button onclick="controlLight('OFF')">关灯</button>
        <script>
            function controlLight(state) {
                fetch('/light/' + state, {method: 'POST'})
                    .then(res => res.json())
                    .then(data => alert(data.status));
            }
        </script>
    ''')

@app.route('/light/<state>', methods=['POST'])
def control_light(state):
    light_controller.write(state)
    logging.info(f"灯光状态设置为：{state}")
    return jsonify({'status': 'success', 'state': state})

@app.route('/status')
def get_status():
    return jsonify({
        'temperature': temp_sensor.read(),
        'light': light_controller.read()
    })

if __name__ == '__main__':
    # 启动线程
    executor.submit(schedule_loop)
    executor.submit(socket_server)
    executor.submit(sensor_producer)
    executor.submit(task_consumer)

    # 启动Flask
    app.run(host='0.0.0.0', port=5000)