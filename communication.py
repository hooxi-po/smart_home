import socket
import json
import logging

class SocketServer:
    def __init__(self, host='0.0.0.0', port=8080, device_manager=None):
        self.host = host
        self.port = port
        self.device_manager = device_manager

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(5)
        logging.info(f"Socket服务器启动，监听端口：{self.port}")
        while True:
            client, addr = server.accept()
            logging.info(f"接收到来自 {addr} 的连接")
            self.handle_client(client)

    def handle_client(self, client):
        data = client.recv(1024).decode()
        try:
            cmd = json.loads(data)
            if cmd['action'] == 'open_light':
                self.device_manager.set_light('ON')
                client.send(json.dumps({'status': 'success'}).encode())
                logging.info("灯光已打开")
            elif cmd['action'] == 'close_light':
                self.device_manager.set_light('OFF')
                client.send(json.dumps({'status': 'success'}).encode())
                logging.info("灯光已关闭")
            else:
                client.send(json.dumps({'error': '未知指令'}).encode())
                logging.warning(f"未知指令：{cmd}")
        except Exception as e:
            client.send(json.dumps({'error': str(e)}).encode())
            logging.error(f"处理Socket请求出错：{e}")
        finally:
            client.close()
