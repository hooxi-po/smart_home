# device_manager.py
from hal_mock import MockHAL, DeviceNotFoundError # 导入我们之前创建的 HAL 和异常
import threading
import time

class DeviceManager:
    """
    设备管理器。
    负责通过 HAL 与设备（模拟的）进行交互，并管理设备信息。
    """
    def __init__(self, hal: MockHAL):
        """
        初始化设备管理器。
        :param hal: 一个实现了 HAL 接口的对象 (这里是 MockHAL 的实例)
        """
        if hal is None:
            raise ValueError("HAL instance cannot be None")
        self.hal = hal
        print("DeviceManager: 初始化完成，使用 MockHAL。")
        # 可以选择在这里从 HAL 获取一次设备列表，或者每次需要时获取
        self._known_devices = self.hal.list_devices()
        print(f"DeviceManager: 发现 {len(self._known_devices)} 个设备: {list(self._known_devices.keys())}")
        # DeviceManager 本身可能也需要锁，如果它管理一些自身的状态，
        # 或者执行需要跨多个 HAL 调用的原子操作。
        # 但如果只是简单地将调用传递给线程安全的 HAL，则可能不需要额外的锁。
        # 为安全起见，可以添加一个锁，尽管在这个简单例子中可能不是绝对必要。
        self._manager_lock = threading.Lock()


    def get_device_state(self, device_id):
        """
        获取指定设备的状态。
        :param device_id: 设备 ID
        :return: 包含状态信息的字典 {'state': ..., 'last_updated': ...}，如果设备不存在则返回 None
        """
        # 可以在这里添加额外的逻辑，比如检查 device_id 格式等
        try:
            # 调用 HAL 来读取实际（模拟的）状态
            state_info = self.hal.read_device(device_id)
            return state_info
        except DeviceNotFoundError:
            print(f"DeviceManager Warning: 设备 {device_id} 未找到。")
            return None
        except Exception as e:
            print(f"DeviceManager Error: 获取设备 {device_id} 状态时出错: {e}")
            return None

    def set_device_state(self, device_id, state):
        """
        设置指定设备的状态。
        :param device_id: 设备 ID
        :param state: 要设置的目标状态 (例如 "on", "off")
        :return: True 如果设置成功，False 如果失败或设备不支持写入
        """
        # 可以在这里添加额外的逻辑，比如检查状态值的有效性
        # 或者根据设备类型决定是否允许写入
        device_type = self._known_devices.get(device_id)
        if device_type == "sensor":
             print(f"DeviceManager Info: 不能直接设置传感器 {device_id} 的状态。")
             return False

        try:
            # 调用 HAL 来写入实际（模拟的）状态
            success = self.hal.write_device(device_id, state)
            return success
        except DeviceNotFoundError:
            print(f"DeviceManager Warning: 设备 {device_id} 未找到。")
            return False
        except Exception as e:
            print(f"DeviceManager Error: 设置设备 {device_id} 状态时出错: {e}")
            return False

    def get_all_devices_status(self):
        """
        获取所有已知设备的状态。
        :return: 一个字典，键是 device_id，值是包含状态的字典 {'state': ..., 'last_updated': ...} 或 None (如果读取失败)
        """
        all_status = {}
        # 使用 manager_lock 保护对 _known_devices 的迭代（虽然在这个例子中它初始化后不变）
        with self._manager_lock:
            known_devices_copy = list(self._known_devices.keys()) # 创建副本以防万一

        print("DeviceManager: 正在获取所有设备状态...")
        for device_id in known_devices_copy:
            status = self.get_device_state(device_id) # 调用自身的方法，包含了错误处理
            all_status[device_id] = status
            # 短暂休眠，避免在模拟读取时过于密集（如果HAL中有模拟延迟或计算）
            # time.sleep(0.01)
        print("DeviceManager: 获取所有设备状态完成。")
        return all_status

    def list_all_devices(self):
        """
        列出所有已知的设备及其类型。
        :return: 一个字典，键是 device_id，值是设备类型
        """
        # 直接从 HAL 获取最新列表可能更准确，如果设备可以动态添加/删除的话
        # 但在这个模拟中，我们假设设备列表是固定的
        # return self.hal.list_devices()
        with self._manager_lock: # 保护对内部状态的访问
            return self._known_devices.copy() # 返回副本

# --- 测试代码 ---
if __name__ == "__main__":
    print("测试 DeviceManager...")
    # 1. 创建 MockHAL 实例
    mock_hal = MockHAL()

    # 2. 用 MockHAL 实例创建 DeviceManager
    device_manager = DeviceManager(mock_hal)

    print("\n列出所有设备:")
    devices = device_manager.list_all_devices()
    print(devices)

    print("\n获取单个设备状态:")
    status = device_manager.get_device_state("light_bedroom")
    if status:
        print(f"卧室灯状态: {status['state']} (上次更新: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status['last_updated']))})")
    status = device_manager.get_device_state("sensor_door_front")
    if status:
        print(f"前门传感器状态: {status['state']}")
    status = device_manager.get_device_state("nonexistent_device") # 测试不存在的设备

    print("\n设置设备状态:")
    success = device_manager.set_device_state("light_bedroom", "on")
    print(f"设置卧室灯 'on' {'成功' if success else '失败'}")
    success = device_manager.set_device_state("sensor_door_front", "open") # 尝试设置传感器
    print(f"尝试设置门传感器 'open' {'成功' if success else '失败'}")
    success = device_manager.set_device_state("nonexistent_device", "on") # 测试不存在的设备
    print(f"尝试设置不存在设备 'on' {'成功' if success else '失败'}")


    print("\n再次获取卧室灯状态:")
    status = device_manager.get_device_state("light_bedroom")
    if status:
        print(f"卧室灯状态: {status['state']}")


    print("\n获取所有设备状态:")
    all_statuses = device_manager.get_all_devices_status()
    for dev_id, status_info in all_statuses.items():
        if status_info:
            print(f"  - {dev_id}: {status_info['state']}")
        else:
            print(f"  - {dev_id}: 获取失败")