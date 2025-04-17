# device_manager.py
# from hal_mock import MockHAL, DeviceNotFoundError # 注释掉旧的
from hal_actual import ActualHAL, DeviceConfigurationError # 导入新的 HAL 和异常
import threading
import time

# 将 DeviceNotFoundError 映射到新的异常（或处理两者）
# 这里选择将 DeviceConfigurationError 视为更通用的错误
DeviceNotFoundError = DeviceConfigurationError # 别名，简化后续代码修改

class DeviceManager:
    """
    设备管理器。
    负责通过 ActualHAL 与设备驱动进行交互，并管理设备信息。
    """
    def __init__(self, hal: ActualHAL): # 类型提示改为 ActualHAL
        """
        初始化设备管理器。
        :param hal: 一个 ActualHAL 的实例
        """
        if hal is None:
            raise ValueError("HAL instance cannot be None")
        self.hal = hal
        print("DeviceManager: 初始化完成，使用 ActualHAL。")

        # 从 HAL 获取设备列表
        try:
            self._known_devices = self.hal.list_devices()
            print(f"DeviceManager: 发现 {len(self._known_devices)} 个设备: {list(self._known_devices.keys())}")
        except Exception as e:
             print(f"DeviceManager Error: 初始化时无法从 HAL 获取设备列表: {e}")
             self._known_devices = {} # 初始化为空字典

        # 使用信号量替代之前的 manager_lock，演示信号量用法
        # 限制同时调用 HAL 的操作数量，例如只允许一个任务同时操作HAL
        self._access_semaphore = threading.Semaphore(1) # 只允许一个线程同时访问 HAL
        print("DeviceManager: 使用信号量限制对 HAL 的并发访问 (value=1)。")


    def get_device_state(self, device_id):
        """
        获取指定设备的状态。
        :param device_id: 设备 ID
        :return: 包含状态信息的字典 {'state': ..., 'last_updated': ...}，如果设备不存在或出错则返回 None
        """
        if device_id not in self._known_devices:
             print(f"DeviceManager Warning: 设备 {device_id} 未在已知设备列表中。")
             return None

        print(f"DeviceManager: 请求获取设备 {device_id} 状态，等待信号量...")
        with self._access_semaphore: # 获取信号量
            print(f"DeviceManager: 获得信号量，调用 HAL 获取 {device_id} 状态...")
            try:
                state_info = self.hal.read_device(device_id)
                print(f"DeviceManager: HAL 返回 {device_id} 状态: {state_info}")
                return state_info
            except DeviceNotFoundError as e: # 捕捉新的/别名的异常
                print(f"DeviceManager Warning: 设备 {device_id} 未找到或配置错误: {e}")
                return None
            except Exception as e:
                # 捕捉 HAL 可能引发的其他潜在异常
                print(f"DeviceManager Error: 获取设备 {device_id} 状态时 HAL 出错: {e}")
                return None
            finally:
                 print(f"DeviceManager: 释放 {device_id} 状态获取的信号量。")


    def set_device_state(self, device_id, state):
        """
        设置指定设备的状态。
        :param device_id: 设备 ID
        :param state: 要设置的目标状态 (例如 "on", "off")
        :return: True 如果设置成功，False 如果失败或设备不支持写入
        """
        device_type = self._known_devices.get(device_id)
        if not device_type:
             print(f"DeviceManager Warning: 设备 {device_id} 未在已知设备列表中。")
             return False

        # 根据设备类型决定是否允许写入 (这个逻辑也可以放在HAL层)
        if device_type == "sensor_temp": # 使用 HAL 返回的类型
             print(f"DeviceManager Info: 不能直接设置传感器 {device_id} 的状态。")
             return False

        print(f"DeviceManager: 请求设置设备 {device_id} 状态为 '{state}'，等待信号量...")
        with self._access_semaphore: # 获取信号量
            print(f"DeviceManager: 获得信号量，调用 HAL 设置 {device_id} 状态...")
            try:
                success = self.hal.write_device(device_id, state)
                print(f"DeviceManager: HAL 返回设置 {device_id} 结果: {success}")
                return success
            except DeviceNotFoundError as e: # 捕捉新的/别名的异常
                print(f"DeviceManager Warning: 设备 {device_id} 未找到或配置错误: {e}")
                return False
            except Exception as e:
                 # 捕捉 HAL 可能引发的其他潜在异常
                print(f"DeviceManager Error: 设置设备 {device_id} 状态时 HAL 出错: {e}")
                return False
            finally:
                 print(f"DeviceManager: 释放 {device_id} 状态设置的信号量。")


    def get_all_devices_status(self):
        """
        获取所有已知设备的状态。
        :return: 一个字典，键是 device_id，值是包含状态的字典或 None
        """
        all_status = {}
        # 获取已知设备列表的副本
        known_devices_copy = list(self._known_devices.keys())

        print("DeviceManager: 正在获取所有设备状态...")
        # 注意：这里每次获取状态都会单独请求信号量
        # 如果需要原子性地获取所有状态，信号量逻辑需要调整
        for device_id in known_devices_copy:
            # 调用自身的 get_device_state，它包含了信号量和错误处理
            status = self.get_device_state(device_id)
            all_status[device_id] = status
            # 短暂休眠，避免过于频繁地访问设备文件（可选）
            time.sleep(0.05)
        print("DeviceManager: 获取所有设备状态完成。")
        return all_status

    def list_all_devices(self):
        """
        列出所有已知的设备及其类型。
        :return: 一个字典，键是 device_id，值是设备类型
        """
        # 返回已知设备列表的副本
        # 如果 HAL 支持动态发现，这里可能需要重新调用 HAL
        return self._known_devices.copy()

# --- 测试代码 (保持不变，但会使用 ActualHAL) ---
if __name__ == "__main__":
    print("测试 DeviceManager (使用 ActualHAL)...")

    # *** 重要: 运行此测试前，请确保 C 驱动已编译并加载 (sudo insmod ...) ***
    # *** 并且设备文件 /dev/smart_* 存在且权限正确 (e.g., sudo chmod 666 /dev/smart_*) ***

    # 0. 定义设备配置
    device_config = {
        "light_livingroom": {"path": "/dev/light_livingroom", "type": "light"},
        "light_bedroom":    {"path": "/dev/light_bedroom",    "type": "light"},
        "socket_kitchen":   {"path": "/dev/socket_kitchen",   "type": "socket"},
        "sensor_temp_main": {"path": "/dev/sensor_temp_main", "type": "sensor_temp"},
    }

    try:
        # 1. 创建 ActualHAL 实例
        actual_hal = ActualHAL(device_config)

        # 2. 用 ActualHAL 实例创建 DeviceManager
        device_manager = DeviceManager(actual_hal)

        print("\n列出所有设备:")
        devices = device_manager.list_all_devices()
        print(devices)

        print("\n获取单个设备状态:")
        status = device_manager.get_device_state("light_bedroom")
        if status:
            print(f"卧室灯状态: {status['state']} (上次更新: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status['last_updated']))})")
        status = device_manager.get_device_state("sensor_temp_main")
        if status:
            print(f"主温传感器状态: {status['state']}")
        status = device_manager.get_device_state("nonexistent_device") # 测试不存在的设备ID

        print("\n设置设备状态:")
        success = device_manager.set_device_state("light_bedroom", "on")
        print(f"设置卧室灯 'on' {'成功' if success else '失败'}")
        success = device_manager.set_device_state("sensor_temp_main", "open") # 尝试设置传感器
        print(f"尝试设置门传感器 'open' {'成功' if success else '失败'}")
        success = device_manager.set_device_state("nonexistent_device", "on") # 测试不存在的设备ID
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

    except DeviceConfigurationError as e:
         print(f"DeviceManager 测试因 HAL 初始化失败而中止: {e}")
    except ValueError as e:
         print(f"DeviceManager 初始化失败: {e}")
    except Exception as e:
         print(f"DeviceManager 测试中发生意外错误: {e}")

    print("\nDeviceManager 测试完成。")