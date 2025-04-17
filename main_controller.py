# main_controller.py (修改版)
import schedule
import time
import threading
import functools
import socketserver
import json
import sys
import shlex
import signal # 导入信号处理模块

# 从之前的模块导入类
# from hal_mock import MockHAL, DeviceNotFoundError # 旧的
from hal_actual import ActualHAL, DeviceConfigurationError # 新的
from device_manager import DeviceManager

# 同样，将 DeviceNotFoundError 映射到 DeviceConfigurationError
DeviceNotFoundError = DeviceConfigurationError

# --- 设备配置 (重要：需要与 C 驱动一致) ---
DEVICE_CONFIG = {
    "light_livingroom": {"path": "/dev/light_livingroom", "type": "light"},
    "light_bedroom":    {"path": "/dev/light_bedroom",    "type": "light"},
    "socket_kitchen":   {"path": "/dev/socket_kitchen",   "type": "socket"},
    "sensor_temp_main": {"path": "/dev/sensor_temp_main", "type": "sensor_temp"},
}

# --- 全局停止事件 ---
stop_event = threading.Event()

# --- 信号处理函数 ---
def handle_signal(signum, frame):
    signal_name = signal.Signals(signum).name
    print(f"\nMain Controller: 收到信号 {signal_name} ({signum})，准备关闭...")
    stop_event.set() # 设置停止事件，通知所有线程

# --- 网络通信部分 (保持不变) ---
class ThreadingTCPServerWithManager(socketserver.ThreadingTCPServer):
    # ... (代码与之前相同) ...
    def __init__(self, server_address, RequestHandlerClass, device_manager, bind_and_activate=True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.device_manager = device_manager
        self.allow_reuse_address = True # 允许地址重用

class SmartHomeControllerTCPHandler(socketserver.BaseRequestHandler):
    # ... (代码与之前相同) ...
    def handle(self):
        client_address = self.client_address
        print(f"Network Server: 接受来自 {client_address} 的连接。")
        device_manager = self.server.device_manager # 从 server 获取 manager
        try:
            while not stop_event.is_set(): # 检查全局停止事件
                # 设置超时，以便在空闲时也能检查 stop_event
                self.request.settimeout(1.0)
                try:
                    data_bytes = self.request.recv(1024).strip()
                    if not data_bytes:
                        print(f"Network Server: 来自 {client_address} 的连接已关闭。")
                        break
                except socketserver.socket.timeout:
                     continue # 超时后继续循环检查 stop_event

                data_str = data_bytes.decode('utf-8')
                print(f"Network Server: 收到来自 {client_address} 的原始数据: {data_str}")
                response = {}
                try:
                    request_json = json.loads(data_str)
                    command = request_json.get('command')
                    # --- JSON 命令处理逻辑 ---
                    if command == 'set':
                        device_id = request_json.get('device_id')
                        state = request_json.get('state')
                        if device_id and state is not None:
                             # 调用 device_manager 处理
                             success = device_manager.set_device_state(device_id, state)
                             response = {"success": success, "message": f"设备 {device_id} 设置为 {state}" if success else f"设置设备 {device_id} 失败"}
                        else: response = {"success": False, "error": "命令 'set' 需要 'device_id' 和 'state' 参数"}

                    elif command == 'get':
                        device_id = request_json.get('device_id')
                        if device_id:
                            # 调用 device_manager 处理
                            state_info = device_manager.get_device_state(device_id)
                            if state_info:
                                 # 转换时间戳以便 JSON 序列化 (可选)
                                 # state_info['last_updated_str'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state_info['last_updated']))
                                 response = {"success": True, "data": state_info}
                            else:
                                 response = {"success": False, "error": f"设备 {device_id} 未找到或获取失败"}
                        else: response = {"success": False, "error": "命令 'get' 需要 'device_id' 参数"}

                    elif command == 'status_all':
                         # 调用 device_manager 处理
                        all_status = device_manager.get_all_devices_status()
                        # 可以添加时间戳转换
                        response = {"success": True, "data": all_status}

                    elif command == 'list_devices':
                         # 调用 device_manager 处理
                        devices = device_manager.list_all_devices()
                        response = {"success": True, "data": devices}

                    elif command == 'ping': response = {"success": True, "message": "pong"}
                    else: response = {"success": False, "error": f"未知命令: {command}"}

                except json.JSONDecodeError: response = {"success": False, "error": "无效的 JSON 格式"}
                except DeviceNotFoundError as e: # 处理设备未找到或配置错误
                     response = {"success": False, "error": f"设备相关错误: {e}"}
                except Exception as e:
                     print(f"Network Server Error: 处理命令时出错: {e}") # 打印详细错误
                     response = {"success": False, "error": f"处理请求时发生内部错误: {str(e)}"}

                # 发送响应
                response_str = json.dumps(response) + "\n"
                self.request.sendall(response_str.encode('utf-8'))
                print(f"Network Server: 已发送响应给 {client_address}: {response_str.strip()}")

        except socketserver.socket.timeout:
            # 这个异常理论上在内部循环处理了，但外部也捕获一下
             pass # print(f"Network Server: 与 {client_address} 的连接因超时关闭 (外部捕获)。")
        except (ConnectionResetError, BrokenPipeError):
             print(f"Network Server: 与 {client_address} 的连接意外断开。")
        except Exception as e:
            # 捕获处理循环中的其他潜在错误
            print(f"Network Server Error: 处理来自 {client_address} 的连接时发生意外错误: {e}")
        finally:
            print(f"Network Server: 结束与 {client_address} 的连接处理。")
            self.request.close()


# --- 任务函数 (逻辑不变, 但依赖的 manager 现在使用 ActualHAL) ---
def set_device_task(device_manager: DeviceManager, device_id: str, state: str):
    print(f"Scheduler: 触发任务 - 设置设备 {device_id} 为 {state}")
    try:
        success = device_manager.set_device_state(device_id, state)
        if not success:
            print(f"Scheduler Warning: 设置设备 {device_id} 状态为 {state} 失败。")
    except Exception as e:
         print(f"Scheduler Error: 执行 set_device_task({device_id}, {state}) 时出错: {e}")

def read_sensor_task(device_manager: DeviceManager, device_id: str):
    print(f"Scheduler: 触发任务 - 读取传感器 {device_id}")
    try:
        state_info = device_manager.get_device_state(device_id)
        if state_info:
            current_time_str = time.strftime('%H:%M:%S', time.localtime(state_info['last_updated']))
            print(f"Scheduler Info: 传感器 {device_id} 当前状态: {state_info['state']} (读取于 {current_time_str})")
        else:
            print(f"Scheduler Warning: 读取传感器 {device_id} 失败。")
    except Exception as e:
         print(f"Scheduler Error: 执行 read_sensor_task({device_id}) 时出错: {e}")

# 模拟灯闪烁的任务
def toggle_light_task(device_manager: DeviceManager, device_id: str):
     print(f"Scheduler: 触发任务 - 切换设备 {device_id} 状态")
     try:
          current_state_info = device_manager.get_device_state(device_id)
          if current_state_info:
               current_state = current_state_info['state']
               next_state = "off" if current_state == "on" else "on"
               print(f"Scheduler: 正在将 {device_id} 从 {current_state} 切换到 {next_state}")
               success = device_manager.set_device_state(device_id, next_state)
               if not success:
                    print(f"Scheduler Warning: 切换设备 {device_id} 状态失败。")
          else:
               print(f"Scheduler Warning: 无法获取 {device_id} 的当前状态来切换。")
     except Exception as e:
          print(f"Scheduler Error: 执行 toggle_light_task({device_id}) 时出错: {e}")


# --- 调度器运行函数 (不变, 依赖 stop_event) ---
def run_scheduler(stop_event: threading.Event):
    print("Scheduler: 调度器线程已启动，每秒检查一次任务。")
    while not stop_event.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
             print(f"Scheduler Error: 运行待定任务时出错: {e}") # 捕获调度本身的错误
        # 使用带有超时的 sleep，这样 stop_event 能更快被检测到
        # time.sleep(1) # schedule 库自己处理等待，这里不需要 sleep
        # 但是为了能及时响应 stop_event，我们自己加一个短等待
        stop_event.wait(1.0) # 等待1秒或直到事件被设置
    print("Scheduler: 调度器线程已停止。")


# --- CLI 运行函数 (修改以更好地处理退出) ---
def run_cli(device_manager: DeviceManager, stop_event: threading.Event):
    """运行命令行界面，接收用户输入并执行命令"""
    print("CLI: 命令行界面已启动。输入 'help' 获取帮助，输入 'exit' 或按 Ctrl+C 退出。")
    while not stop_event.is_set():
        try:
            # input() 会阻塞，如果主线程收到信号设置了 stop_event，
            # 这个线程可能不会立即退出，直到用户按回车。
            # 可以考虑使用 select 或其他非阻塞方式读取 stdin，但会增加复杂度。
            # 目前接受这种延迟。
            command_line = input("Controller> ")
            if stop_event.is_set(): # 在 input 返回后再次检查
                 break

            if not command_line:
                continue

            try:
                 parts = shlex.split(command_line)
            except ValueError as e:
                 print(f"CLI Error: 解析命令时出错（可能是引号未闭合）: {e}")
                 continue
            if not parts: continue

            command = parts[0].lower()
            args = parts[1:]

            # --- 处理命令 ---
            if command == "help":
                # ... (help 信息不变) ...
                print("可用命令:")
                print("  help                          - 显示此帮助信息")
                print("  list                          - 列出所有已知设备及其类型")
                print("  status <device_id> / all    - 显示指定设备或所有设备的状态")
                print("  open <device_id>              - 打开设备 (如灯、插座)")
                print("  close <device_id>             - 关闭设备 (如灯、插座)")
                print("  set <device_id> <state>       - 设置设备状态 (通用，小心使用)")
                print("  exit / quit                   - 关闭控制器")

            elif command == "list":
                 # ... (list 实现不变，调用 manager) ...
                 devices = device_manager.list_all_devices()
                 if devices:
                     print("已知设备:")
                     for dev_id, dev_type in devices.items():
                         print(f"  - {dev_id} (类型: {dev_type})")
                 else:
                     print("没有找到已知设备。")

            elif command == "status":
                 # ... (status 实现不变，调用 manager) ...
                if not args:
                    print("用法: status <device_id> 或 status all")
                elif args[0].lower() == "all":
                    all_status = device_manager.get_all_devices_status()
                    print("所有设备状态:")
                    if not all_status:
                         print("  (无法获取任何设备状态)")
                    for dev_id, status_info in all_status.items():
                         if status_info:
                             state = status_info['state']
                             ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status_info['last_updated']))
                             print(f"  - {dev_id}: {state} (更新于 {ts})")
                         else:
                             print(f"  - {dev_id}: 获取失败")
                else:
                    device_id = args[0]
                    status_info = device_manager.get_device_state(device_id)
                    if status_info:
                        state = status_info['state']
                        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status_info['last_updated']))
                        print(f"设备 {device_id} 状态: {state} (更新于 {ts})")
                    else:
                        print(f"无法获取设备 {device_id} 的状态 (可能不存在或错误)")


            elif command == "open":
                 # ... (open 实现不变，调用 manager) ...
                if len(args) != 1: print("用法: open <device_id>")
                else:
                    device_id = args[0]
                    success = device_manager.set_device_state(device_id, "on")
                    print(f"命令执行 {'成功' if success else '失败'}")

            elif command == "close":
                 # ... (close 实现不变，调用 manager) ...
                if len(args) != 1: print("用法: close <device_id>")
                else:
                    device_id = args[0]
                    success = device_manager.set_device_state(device_id, "off")
                    print(f"命令执行 {'成功' if success else '失败'}")

            elif command == "set":
                 # ... (set 实现不变，调用 manager) ...
                 if len(args) != 2: print("用法: set <device_id> <state>")
                 else:
                     device_id, state = args[0], args[1]
                     success = device_manager.set_device_state(device_id, state)
                     print(f"命令执行 {'成功' if success else '失败'}")


            elif command in ["exit", "quit"]:
                print("CLI: 收到退出命令，正在通知主程序关闭...")
                stop_event.set() # 设置停止事件
                break # 退出 CLI 循环

            else:
                print(f"CLI Error: 未知命令 '{command}'. 输入 'help' 查看可用命令。")

        except EOFError: # 用户按 Ctrl+D
             print("\nCLI: 检测到 EOF，正在退出...")
             stop_event.set()
             break
        # 不需要在这里捕获 KeyboardInterrupt，让信号处理程序来做
        # except KeyboardInterrupt:
        #      print("\nCLI: 检测到中断，正在退出...")
        #      stop_event.set()
        #      break
        except Exception as e:
             # 捕获其他可能的错误，例如 DeviceManager 调用中的错误
             print(f"CLI Error: 处理命令时发生错误: {e}")
             # 如果错误严重，可能也需要考虑设置 stop_event
             # stop_event.set()
             # break

    print("CLI: 命令行界面线程已停止。")


# --- 主程序设置 ---
if __name__ == "__main__":
    print("Main Controller: 启动...")
    HOST, PORT = "localhost", 9998 # 或者 "0.0.0.0" 监听所有接口
    current_time_local = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
    current_time_utc = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    print(f"Main Controller: 当前本地时间: {current_time_local}")
    print(f"Main Controller: 当前UTC时间: {current_time_utc}")
    print("-" * 30)
    print("Main Controller: *** 请确保 C 驱动已加载且 /dev/smart_* 权限正确 ***")
    print("-" * 30)

    # --- 注册信号处理程序 ---
    try:
        signal.signal(signal.SIGTERM, handle_signal) # 处理 kill 命令
        signal.signal(signal.SIGINT, handle_signal)  # 处理 Ctrl+C
        print("Main Controller: 已注册 SIGTERM 和 SIGINT 信号处理程序。")
    except ValueError:
         print("Main Controller Warning: 在非主线程中？无法完全注册信号处理程序。") # 在某些环境（如 Windows 或非主线程）可能失败
    except Exception as e:
         print(f"Main Controller Warning: 注册信号处理程序时出错: {e}")

    # --- 初始化组件 ---
    hal = None
    device_manager = None
    scheduler_thread = None
    server_thread = None
    cli_thread = None
    server = None # 初始化 server 变量

    try:
        # 1. 初始化 ActualHAL 和 DeviceManager
        print("Main Controller: 初始化 ActualHAL...")
        try:
            hal = ActualHAL(DEVICE_CONFIG)
        except DeviceConfigurationError as e:
             print(f"Main Controller FATAL: HAL 初始化失败: {e}")
             print("请确保 C 驱动 'smart_device_driver.ko' 已加载 (sudo insmod) 并且设备文件 /dev/smart_* 存在且权限正确 (e.g., sudo chmod 666 /dev/smart_*)")
             sys.exit(1)
        except Exception as e:
             print(f"Main Controller FATAL: HAL 初始化时发生未知错误: {e}")
             sys.exit(1)

        print("Main Controller: 初始化 DeviceManager...")
        try:
             device_manager = DeviceManager(hal)
        except ValueError as e:
             print(f"Main Controller FATAL: DeviceManager 初始化失败: {e}")
             sys.exit(1)
        except Exception as e:
             print(f"Main Controller FATAL: DeviceManager 初始化时发生未知错误: {e}")
             sys.exit(1)
        print("-" * 30)

        # 2. 配置调度任务 (使用 functools.partial 传递 manager)
        print("Main Controller: 配置调度任务...")
        # 定时开关客厅灯
        schedule.every().day.at("19:00").do(functools.partial(set_device_task, device_manager, "light_livingroom", "on"))
        schedule.every().day.at("23:30").do(functools.partial(set_device_task, device_manager, "light_livingroom", "off"))
        # 定时开关卧室灯
        schedule.every().day.at("07:00").do(functools.partial(set_device_task, device_manager, "light_bedroom", "on"))
        schedule.every().day.at("09:00").do(functools.partial(set_device_task, device_manager, "light_bedroom", "off"))
        # 每 30 秒读取一次温度传感器
        schedule.every(30).seconds.do(functools.partial(read_sensor_task, device_manager, "sensor_temp_main"))
        # 每 15 秒切换一次厨房插座状态 (用于测试)
        # schedule.every(15).seconds.do(functools.partial(toggle_light_task, device_manager, "socket_kitchen")) # 注意toggle函数需要实现
        print("  - 任务配置完成。")
        print("-" * 30)

        # 3. 启动调度器线程
        print("Main Controller: 启动调度器线程...")
        scheduler_thread = threading.Thread(target=run_scheduler, args=(stop_event,), daemon=True)
        scheduler_thread.start()
        print("-" * 30)

        # 4. 启动网络服务器线程
        print("Main Controller: 启动网络服务器线程...")
        # 创建自定义的 TCP Handler，将 device_manager 传递给它
        handler_with_manager = functools.partial(SmartHomeControllerTCPHandler)
        # 创建服务器实例，将 device_manager 关联到服务器
        server = ThreadingTCPServerWithManager((HOST, PORT), handler_with_manager, device_manager)

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print(f"Network Server: 服务器已在 {HOST}:{PORT} 启动并监听...")
        print("-" * 30)

        # 5. 启动 CLI 线程 (非守护线程)
        print("Main Controller: 启动 CLI 线程...")
        cli_thread = threading.Thread(target=run_cli, args=(device_manager, stop_event))
        cli_thread.start()
        print("-" * 30)

        # 6. 主线程等待退出信号
        print("Main Controller: 主线程等待退出信号 (来自 CLI 'exit' 或 Ctrl+C)...")
        # 使用 stop_event.wait() 使主线程阻塞，直到事件被设置
        stop_event.wait()
        print("\nMain Controller: 检测到退出信号，正在执行关闭流程...")

    # 不再需要单独捕获 KeyboardInterrupt，因为它会被信号处理器捕获并设置 stop_event
    # except KeyboardInterrupt:
    #     print("\nMain Controller: 在主线程检测到 Ctrl+C，正在关闭...")
    #     if not stop_event.is_set(): stop_event.set()
    except Exception as e:
         # 捕获初始化或主循环中（虽然这里主要是等待）的其他错误
         print(f"\nMain Controller: 发生意外严重错误: {e}")
         if not stop_event.is_set(): stop_event.set() # 确保触发关闭流程

    finally:
        # --- 关闭流程 ---
        print("Main Controller: 开始关闭所有组件...")

        # 1. 停止调度器 (通过 stop_event 通知，等待线程结束)
        if scheduler_thread and scheduler_thread.is_alive():
            print("Main Controller: 正在停止调度器...")
            # schedule.clear() # 清理任务是可选的，线程退出即可
            scheduler_thread.join(timeout=2)
            if scheduler_thread.is_alive():
                 print("Main Controller Warning: 调度器线程未能及时停止。")

        # 2. 关闭网络服务器
        if server: # 检查 server 是否已成功创建
            print("Main Controller: 正在关闭网络服务器...")
            server.shutdown() # 停止接受新连接，并让当前处理完成（有超时）
            server.server_close() # 关闭服务器socket
            if server_thread and server_thread.is_alive():
                 # server.shutdown() 应该会让 serve_forever 返回，线程自然结束
                 server_thread.join(timeout=2)
                 if server_thread.is_alive():
                      print("Main Controller Warning: 网络服务器线程未能及时停止。")


        # 3. 等待 CLI 线程结束
        # CLI 线程在输入 exit 或收到 stop_event 后应自行退出其循环
        if cli_thread and cli_thread.is_alive():
            print("Main Controller: 正在等待 CLI 线程退出 (可能需要按回车)...")
            # 不需要强制停止，等待它自然结束
            cli_thread.join(timeout=5) # 等待最多5秒
            if cli_thread.is_alive():
                 print("Main Controller Warning: CLI 线程未能及时停止 (可能卡在input?)。")

        print("Main Controller: 服务已停止。程序结束。")
        sys.exit(0) # 确保程序退出