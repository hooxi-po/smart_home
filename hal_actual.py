# hal_actual.py
import os
import time
import threading
import errno

class DeviceConfigurationError(Exception):
    """自定义异常，表示设备配置或访问问题"""
    pass

class ActualHAL:
    """
    实际硬件抽象层 (Actual Hardware Abstraction Layer)。
    通过 Linux 字符设备驱动程序与模拟的硬件交互。
    """
    def __init__(self, device_config):
        """
        初始化 ActualHAL。
        :param device_config: 字典，包含设备ID到设备文件路径和类型的映射。
                              例如: {'light_livingroom': {'path': '/dev/light_livingroom', 'type': 'light'}, ...}
        """
        self._device_config = device_config
        # 使用信号量来限制对底层设备文件的并发访问（如果需要）
        # 这里设置为允许5个并发访问，可以根据实际情况调整
        self._hal_semaphore = threading.Semaphore(5)
        print("ActualHAL: 初始化完成，使用以下设备配置:")
        for dev_id, config in self._device_config.items():
            print(f"  - {dev_id} ({config['type']}) -> {config['path']}")
        self._validate_devices() # 检查设备文件是否存在

    def _validate_devices(self):
        """检查配置中的设备文件是否存在且可访问"""
        print("ActualHAL: 正在验证设备节点...")
        all_found = True
        for dev_id, config in self._device_config.items():
            path = config['path']
            if not os.path.exists(path):
                print(f"ActualHAL Error: 设备节点 {path} (for {dev_id}) 不存在！")
                all_found = False
            elif not os.access(path, os.R_OK | os.W_OK):
                 # 检查读写权限 (对于传感器可能只需要读权限)
                 # 简化处理：假设都需要读写，如果权限不足则警告
                 print(f"ActualHAL Warning: 设备节点 {path} (for {dev_id}) 权限不足 (需要rw)。")
                 # all_found = False # 可以选择是否因为权限不足而失败
        if not all_found:
             # 注意：这里可以选择抛出异常或仅打印警告
             # raise DeviceConfigurationError("一个或多个设备节点不存在或权限不足。请检查驱动是否加载且权限设置正确。")
             print("ActualHAL Error: 一个或多个设备节点不存在或权限不足。请检查驱动是否加载且权限设置正确。")
        else:
             print("ActualHAL: 设备节点验证通过。")


    def _get_device_path(self, device_id):
        """根据设备ID获取设备文件路径"""
        config = self._device_config.get(device_id)
        if not config:
            raise DeviceConfigurationError(f"设备ID '{device_id}' 未在配置中找到")
        return config['path']

    def read_device(self, device_id):
        """
        从字符设备驱动读取状态或数据。
        """
        path = self._get_device_path(device_id)
        print(f"ActualHAL: 尝试读取设备 {device_id} 从 {path}")
        with self._hal_semaphore: # 获取信号量
            try:
                # 注意：对字符设备文件使用 'r' 或 'rb' 模式取决于驱动实现和数据格式
                # 我们的驱动返回文本，所以用 'r'
                with open(path, 'r') as f:
                    # 驱动的 read 实现简单，一次读取所有内容
                    state_str = f.read().strip()
                    # 对于传感器，可以尝试转换为浮点数
                    current_time = time.time()
                    # print(f"ActualHAL: 从 {device_id} 读取原始值: '{state_str}'") # 调试信息

                    # 可以根据设备类型尝试解析状态
                    device_type = self._device_config[device_id]['type']
                    if device_type == 'sensor_temp':
                         try:
                             state = float(state_str)
                         except ValueError:
                             print(f"ActualHAL Warning: 无法将传感器 '{device_id}' 的值 '{state_str}' 解析为浮点数。")
                             state = state_str # 保持原样
                    elif device_type in ['light', 'socket']:
                         state = state_str # "on" or "off"
                    else:
                         state = state_str # 其他类型直接返回字符串

                    print(f"ActualHAL: 读取设备 {device_id}, 解析状态: {state}")
                    return {"state": state, "last_updated": current_time}

            except FileNotFoundError:
                print(f"ActualHAL Error: 设备文件 {path} (for {device_id}) 未找到。驱动是否加载？")
                raise DeviceConfigurationError(f"设备文件 {path} 未找到")
            except PermissionError:
                 print(f"ActualHAL Error: 没有权限读取设备文件 {path} (for {device_id})。")
                 raise DeviceConfigurationError(f"没有权限读取设备文件 {path}")
            except OSError as e:
                 # 处理其他可能的OS错误，例如驱动返回错误
                 print(f"ActualHAL Error: 读取设备 {path} (for {device_id}) 时发生 OS 错误: {e}")
                 if e.errno == errno.ENODEV: # No such device (驱动可能返回此错误)
                      raise DeviceConfigurationError(f"设备 {path} 不存在或驱动错误")
                 else:
                      raise # 重新引发未处理的 OSError
            except Exception as e:
                print(f"ActualHAL Error: 读取设备 {device_id} 时发生未知错误: {e}")
                raise # 重新引发未知错误

    def write_device(self, device_id, state):
        """
        向字符设备驱动写入状态或命令。
        """
        config = self._device_config.get(device_id)
        if not config:
            raise DeviceConfigurationError(f"设备ID '{device_id}' 未在配置中找到")

        path = config['path']
        device_type = config['type']

        # 检查是否允许写入
        if device_type not in ['light', 'socket']:
            print(f"ActualHAL Info: 设备 {device_id} (类型: {device_type}) 不支持写入。")
            return False

        # 状态转换为驱动期望的格式 (字符串 "on" 或 "off")
        if isinstance(state, bool):
            state_str = "on" if state else "off"
        elif isinstance(state, str) and state.lower() in ["on", "off", "1", "0"]:
            state_str = state.lower()
            # 可以规范化为 "on" / "off"
            if state_str == "1": state_str = "on"
            if state_str == "0": state_str = "off"
        else:
            print(f"ActualHAL Error: 无效的状态 '{state}' 用于设备 {device_id}")
            return False

        print(f"ActualHAL: 尝试向设备 {device_id} ({path}) 写入状态: '{state_str}'")
        with self._hal_semaphore: # 获取信号量
            try:
                # 使用 'w' 模式打开，驱动的 write 会处理这个字符串
                with open(path, 'w') as f:
                    bytes_written = f.write(state_str) # write 通常需要字符串
                    # f.flush() # 确保写入完成，对于设备文件可能不需要
                print(f"ActualHAL: 成功向 {device_id} 写入 {bytes_written} 字节。")
                return True
            except FileNotFoundError:
                print(f"ActualHAL Error: 设备文件 {path} (for {device_id}) 未找到。驱动是否加载？")
                raise DeviceConfigurationError(f"设备文件 {path} 未找到")
            except PermissionError:
                 print(f"ActualHAL Error: 没有权限写入设备文件 {path} (for {device_id})。")
                 raise DeviceConfigurationError(f"没有权限写入设备文件 {path}")
            except OSError as e:
                 # 处理可能的OS错误，例如驱动返回错误
                 print(f"ActualHAL Error: 写入设备 {path} (for {device_id}) 时发生 OS 错误: {e}")
                 # 例如，如果驱动的 write 返回错误码，可能会触发 OSError
                 # ENODEV: No such device
                 # EPERM: Operation not permitted (e.g., writing to sensor)
                 # EINVAL: Invalid argument (e.g., writing invalid state "dim")
                 return False # 写入失败
            except Exception as e:
                print(f"ActualHAL Error: 写入设备 {device_id} 时发生未知错误: {e}")
                return False # 写入失败

    def list_devices(self):
        """返回配置中定义的设备ID和类型"""
        return {dev_id: data["type"] for dev_id, data in self._device_config.items()}

# --- 测试代码 (可选) ---
if __name__ == "__main__":
    print("测试 ActualHAL...")

    # *** 重要: 运行此测试前，请确保 C 驱动已编译并加载 (sudo insmod ...) ***
    # *** 并且设备文件 /dev/smart_* 存在且权限正确 (e.g., sudo chmod 666 /dev/smart_*) ***

    # 定义设备配置，路径需要与 C 驱动创建的一致
    config = {
        "light_livingroom": {"path": "/dev/light_livingroom", "type": "light"},
        "light_bedroom":    {"path": "/dev/light_bedroom",    "type": "light"},
        "socket_kitchen":   {"path": "/dev/socket_kitchen",   "type": "socket"},
        "sensor_temp_main": {"path": "/dev/sensor_temp_main", "type": "sensor_temp"},
        #"nonexistent_device": {"path": "/dev/nonexistent", "type": "unknown"} # 测试不存在
    }

    try:
        hal = ActualHAL(config)

        print("\n列出设备:")
        devices = hal.list_devices()
        print(devices)

        print("\n读取设备状态:")
        try:
            status = hal.read_device("light_livingroom")
            print(f"客厅灯状态: {status}")
            status = hal.read_device("sensor_temp_main")
            print(f"主温传感器状态: {status}")
            # 多次读取传感器
            for _ in range(3):
                 time.sleep(1.1) # 等待时间长一点，让模拟值变化
                 status = hal.read_device("sensor_temp_main")
                 print(f"主温传感器状态更新: {status}")
        except DeviceConfigurationError as e:
            print(e)
        # except KeyError as e:
        #     print(f"测试错误: 设备ID {e} 未在配置中?") # 如果配置错误

        print("\n写入设备状态:")
        try:
            hal.write_device("light_livingroom", "on")
            hal.write_device("socket_kitchen", "on")
            hal.write_device("sensor_temp_main", "30") # 尝试写入传感器 (应失败)
            # hal.write_device("light_nonexistent", "on") # 尝试写入不存在的设备ID (会因配置检查失败)
            # hal.write_device("light_bedroom", "invalid_state") # 尝试写入无效状态
        except DeviceConfigurationError as e:
            print(e)


        print("\n再次读取状态:")
        try:
            status = hal.read_device("light_livingroom")
            print(f"客厅灯状态: {status}")
            status = hal.read_device("socket_kitchen")
            print(f"厨房插座状态: {status}")
        except DeviceConfigurationError as e:
            print(e)

    except DeviceConfigurationError as e:
         print(f"HAL 初始化失败: {e}")
    except Exception as e:
         print(f"发生意外错误: {e}")

    print("\n测试完成。卸载驱动: sudo rmmod smart_device_driver")