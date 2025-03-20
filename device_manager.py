import logging

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

class DeviceManager:
    def __init__(self):
        self.temp_sensor = VirtualDevice('./virtual_devices/sensor_temp')
        self.light_controller = VirtualDevice('./virtual_devices/light_ctl')

    def get_temperature(self):
        return self.temp_sensor.read()

    def set_light(self, state):
        self.light_controller.write(state)

    def get_light_status(self):
        return self.light_controller.read()
