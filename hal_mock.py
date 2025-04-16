# hal_mock.py
import time
import random
import threading

class DeviceNotFoundError(Exception):
    """自定义异常，表示设备未找到"""
    pass

class MockHAL:
    """
    模拟硬件抽象层 (Mock Hardware Abstraction Layer)。
    它不与真实硬件交互，而是维护一个内部状态字典来模拟设备。
    """
    def __init__(self):
        # _device_states 存储模拟设备及其当前状态
        # 格式: {'device_id': {'type': 'light'/'sensor', 'state': value, 'last_updated': timestamp}}
        self._device_states = {
            "light_livingroom": {"type": "light", "state": "off", "last_updated": time.time()},
            "light_bedroom":    {"type": "light", "state": "off", "last_updated": time.time()},
            "socket_kitchen":   {"type": "socket", "state": "off", "last_updated": time.time()},
            "sensor_temp_ hlavní": {"type": "sensor", "state": 22.5, "last_updated": time.time()}, # 模拟温度传感器
            "sensor_door_front": {"type": "sensor", "state": "closed", "last_updated": time.time()} # 模拟门磁传感器
        }
        # 使用锁来保护对 _device_states 的并发访问
        self._lock = threading.Lock()
        print("MockHAL: 初始化完成，模拟设备状态:")
        for device_id, data in self._device_states.items():
            print(f"  - {device_id} ({data['type']}): {data['state']}")

    def read_device(self, device_id):
        """
        模拟从设备读取状态或数据。
        """
        with self._lock: # 获取锁，保证线程安全
            if device_id not in self._device_states:
                print(f"MockHAL Error: 尝试读取不存在的设备 {device_id}")
                raise DeviceNotFoundError(f"设备 {device_id} 未找到")

            device_info = self._device_states[device_id]
            device_type = device_info["type"]

            # 模拟传感器读数的一些随机变化
            if device_type == "sensor":
                current_state = device_info["state"]
                if isinstance(current_state, (int, float)): # 如温度
                    # 轻微随机波动
                    new_state = round(current_state + random.uniform(-0.2, 0.2), 1)
                    # 模拟一个缓慢的变化趋势
                    if random.random() < 0.1: # 10% 概率
                        new_state += random.choice([-0.5, 0.5])
                    # 限制在合理范围 (假设是温度)
                    new_state = max(10.0, min(35.0, new_state))
                    device_info["state"] = new_state
                    device_info["last_updated"] = time.time()
                elif isinstance(current_state, str): # 如门磁
                    # 模拟状态随机变化 (例如门被打开/关闭)
                    if random.random() < 0.05: # 5% 概率状态改变
                         device_info["state"] = "open" if current_state == "closed" else "closed"
                         device_info["last_updated"] = time.time()

            print(f"MockHAL: 读取设备 {device_id}, 当前状态: {device_info['state']}")
            # 返回设备当前状态和最后更新时间
            return {"state": device_info["state"], "last_updated": device_info["last_updated"]}

    def write_device(self, device_id, state):
        """
        模拟向设备写入状态或命令。
        """
        with self._lock: # 获取锁
            if device_id not in self._device_states:
                print(f"MockHAL Error: 尝试写入不存在的设备 {device_id}")
                raise DeviceNotFoundError(f"设备 {device_id} 未找到")

            device_info = self._device_states[device_id]
            device_type = device_info["type"]

            # 检查状态是否适用于设备类型
            if device_type == "light" or device_type == "socket":
                if state not in ["on", "off"]:
                    print(f"MockHAL Error: 无效的状态 '{state}' 用于设备 {device_id} (类型: {device_type})")
                    return False # 表示写入失败
                device_info["state"] = state
                device_info["last_updated"] = time.time()
                print(f"MockHAL: 写入设备 {device_id}, 设置状态为: {state}")
                return True # 表示写入成功
            elif device_type == "sensor":
                print(f"MockHAL Error: 不能直接写入传感器设备 {device_id}")
                return False # 传感器通常是只读的
            else:
                # 对于未知类型，也进行更新，但打印警告
                print(f"MockHAL Warning: 尝试写入未知类型的设备 {device_id}, 状态: {state}")
                device_info["state"] = state
                device_info["last_updated"] = time.time()
                return True

    def list_devices(self):
        """返回所有模拟设备的ID和类型"""
        with self._lock:
            return {dev_id: data["type"] for dev_id, data in self._device_states.items()}

# --- 测试代码 ---
if __name__ == "__main__":
    print("测试 MockHAL...")
    hal = MockHAL()

    print("\n列出设备:")
    devices = hal.list_devices()
    print(devices)

    print("\n读取设备状态:")
    try:
        status = hal.read_device("light_livingroom")
        print(f"客厅灯状态: {status}")
        status = hal.read_device("sensor_temp_main")
        print(f"主温传感器状态: {status}")
        # 模拟读取多次传感器
        for _ in range(3):
             time.sleep(0.1)
             status = hal.read_device("sensor_temp_main")
             print(f"主温传感器状态更新: {status}")

    except DeviceNotFoundError as e:
        print(e)

    print("\n写入设备状态:")
    hal.write_device("light_livingroom", "on")
    hal.write_device("socket_kitchen", "on")
    hal.write_device("sensor_temp_main", "30") # 尝试写入传感器 (应失败或警告)
    hal.write_device("light_nonexistent", "on") # 尝试写入不存在的设备

    print("\n再次读取状态:")
    try:
        status = hal.read_device("light_livingroom")
        print(f"客厅灯状态: {status}")
        status = hal.read_device("socket_kitchen")
        print(f"厨房插座状态: {status}")
    except DeviceNotFoundError as e:
        print(e)