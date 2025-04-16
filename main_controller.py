# main_controller.py (添加 CLI 部分)
import schedule
import time
import threading
import functools
import socketserver
import json
import sys
import shlex # 用于更安全地分割命令行输入

# 从之前的模块导入类
from hal_mock import MockHAL, DeviceNotFoundError
from device_manager import DeviceManager

# --- 网络通信部分 (保持不变) ---
class ThreadingTCPServerWithManager(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, device_manager, bind_and_activate=True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.device_manager = device_manager
        self.allow_reuse_address = True

class SmartHomeControllerTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_address = self.client_address
        print(f"Network Server: 接受来自 {client_address} 的连接。")
        device_manager = self.server.device_manager
        try:
            while True:
                self.request.settimeout(600.0) # 延长超时时间
                data_bytes = self.request.recv(1024).strip()
                if not data_bytes:
                    print(f"Network Server: 来自 {client_address} 的连接已关闭。")
                    break
                data_str = data_bytes.decode('utf-8')
                print(f"Network Server: 收到来自 {client_address} 的原始数据: {data_str}")
                response = {}
                try:
                    request_json = json.loads(data_str)
                    command = request_json.get('command')
                    # ... (JSON 命令处理逻辑与上一步相同) ...
                    if command == 'set':
                        device_id = request_json.get('device_id')
                        state = request_json.get('state')
                        if device_id and state is not None:
                             success = device_manager.set_device_state(device_id, state)
                             response = {"success": success, "message": f"设备 {device_id} 设置为 {state}" if success else f"设置设备 {device_id} 失败"}
                        else: response = {"success": False, "error": "命令 'set' 需要 'device_id' 和 'state' 参数"}
                    elif command == 'get':
                        device_id = request_json.get('device_id')
                        if device_id:
                            state_info = device_manager.get_device_state(device_id)
                            response = {"success": True, "data": state_info} if state_info else {"success": False, "error": f"设备 {device_id} 未找到或获取失败"}
                        else: response = {"success": False, "error": "命令 'get' 需要 'device_id' 参数"}
                    elif command == 'status_all':
                        all_status = device_manager.get_all_devices_status()
                        response = {"success": True, "data": all_status}
                    elif command == 'list_devices':
                        devices = device_manager.list_all_devices()
                        response = {"success": True, "data": devices}
                    elif command == 'ping': response = {"success": True, "message": "pong"}
                    else: response = {"success": False, "error": f"未知命令: {command}"}
                except json.JSONDecodeError: response = {"success": False, "error": "无效的 JSON 格式"}
                except Exception as e: response = {"success": False, "error": f"处理请求时发生内部错误: {str(e)}"}
                response_str = json.dumps(response) + "\n"
                self.request.sendall(response_str.encode('utf-8'))
                print(f"Network Server: 已发送响应给 {client_address}: {response_str.strip()}")
        except socketserver.socket.timeout: print(f"Network Server: 与 {client_address} 的连接超时。")
        except Exception as e: print(f"Network Server Error: 处理来自 {client_address} 的连接时发生意外错误: {e}")
        finally:
            print(f"Network Server: 结束与 {client_address} 的连接处理。")
            self.request.close()


# --- 任务函数 (保持不变) ---
def set_device_task(device_manager: DeviceManager, device_id: str, state: str):
    print(f"Scheduler: 触发任务 - 设置设备 {device_id} 为 {state}")
    # ... (内容不变) ...
    success = device_manager.set_device_state(device_id, state)
    if not success: print(f"Scheduler Warning: 设置设备 {device_id} 状态为 {state} 失败。")

def read_sensor_task(device_manager: DeviceManager, device_id: str):
    print(f"Scheduler: 触发任务 - 读取传感器 {device_id}")
    # ... (内容不变) ...
    state_info = device_manager.get_device_state(device_id)
    if state_info: print(f"Scheduler Info: 传感器 {device_id} 当前状态: {state_info['state']} (读取于 {time.strftime('%H:%M:%S', time.localtime(state_info['last_updated']))})")
    else: print(f"Scheduler Warning: 读取传感器 {device_id} 失败。")


# --- 调度器运行函数 (保持不变) ---
def run_scheduler(stop_event: threading.Event): # 明确接收 stop_event
    print("Scheduler: 调度器线程已启动，每秒检查一次任务。")
    while not stop_event.is_set():
        schedule.run_pending()
        # 使用带有超时的 sleep，这样 stop_event 能更快被检测到
        stop_event.wait(1.0) # 等待1秒或直到事件被设置
    print("Scheduler: 调度器线程已停止。")


# --- CLI 运行函数 ---
def run_cli(device_manager: DeviceManager, stop_event: threading.Event):
    """运行命令行界面，接收用户输入并执行命令"""
    print("CLI: 命令行界面已启动。输入 'help' 获取帮助，输入 'exit' 退出。")
    while not stop_event.is_set():
        try:
            # 使用 input() 获取用户输入，它会阻塞当前线程直到用户输入并回车
            command_line = input("Controller> ")
            if not command_line: # 用户直接按回车
                continue

            # 使用 shlex.split 来处理带引号的参数，比简单的 split 更健壮
            try:
                 parts = shlex.split(command_line)
            except ValueError as e:
                 print(f"CLI Error: 解析命令时出错（可能是引号未闭合）: {e}")
                 continue

            if not parts: # 输入了空白字符
                 continue

            command = parts[0].lower() # 命令不区分大小写
            args = parts[1:]

            # --- 处理命令 ---
            if command == "help":
                print("可用命令:")
                print("  help                          - 显示此帮助信息")
                print("  list                          - 列出所有已知设备及其类型")
                print("  status <device_id> / all    - 显示指定设备或所有设备的状态")
                print("  open <device_id>              - 打开设备 (如灯、插座)")
                print("  close <device_id>             - 关闭设备 (如灯、插座)")
                print("  set <device_id> <state>       - 设置设备状态 (通用，小心使用)")
                print("  exit / quit                   - 关闭控制器")

            elif command == "list":
                 devices = device_manager.list_all_devices()
                 if devices:
                     print("已知设备:")
                     for dev_id, dev_type in devices.items():
                         print(f"  - {dev_id} (类型: {dev_type})")
                 else:
                     print("没有找到设备。")

            elif command == "status":
                if not args:
                    print("用法: status <device_id> 或 status all")
                elif args[0].lower() == "all":
                    all_status = device_manager.get_all_devices_status()
                    print("所有设备状态:")
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
                        print(f"无法获取设备 {device_id} 的状态 (可能不存在)")

            elif command == "open":
                if len(args) != 1: print("用法: open <device_id>")
                else:
                    device_id = args[0]
                    success = device_manager.set_device_state(device_id, "on")
                    print(f"命令执行 {'成功' if success else '失败'}")

            elif command == "close":
                if len(args) != 1: print("用法: close <device_id>")
                else:
                    device_id = args[0]
                    success = device_manager.set_device_state(device_id, "off")
                    print(f"命令执行 {'成功' if success else '失败'}")

            elif command == "set":
                 if len(args) != 2: print("用法: set <device_id> <state>")
                 else:
                     device_id, state = args[0], args[1]
                     success = device_manager.set_device_state(device_id, state)
                     print(f"命令执行 {'成功' if success else '失败'}")

            elif command in ["exit", "quit"]:
                print("CLI: 收到退出命令，正在通知主程序关闭...")
                stop_event.set() # 设置停止事件，通知其他线程和主循环退出
                break # 退出 CLI 循环

            else:
                print(f"CLI Error: 未知命令 '{command}'. 输入 'help' 查看可用命令。")

        except EOFError: # 用户按 Ctrl+D
             print("\nCLI: 检测到 EOF，正在退出 CLI...")
             stop_event.set() # 也触发关闭
             break
        except KeyboardInterrupt: # 用户在 CLI 提示符下按 Ctrl+C
             print("\nCLI: 检测到中断，正在退出 CLI...")
             stop_event.set() # 也触发关闭
             break
        except Exception as e:
             print(f"CLI Error: 处理命令时发生错误: {e}")

    print("CLI: 命令行界面线程已停止。")


# --- 主程序设置 ---
if __name__ == "__main__":
    print("Main Controller: 启动...")
    HOST, PORT = "localhost", 9998
    current_time_local = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
    current_time_utc = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    print(f"Main Controller: 当前本地时间: {current_time_local}")
    print(f"Main Controller: 当前UTC时间: {current_time_utc}")

    stop_event = threading.Event()

    # 1. 初始化 HAL 和 DeviceManager
    hal = MockHAL()
    device_manager = DeviceManager(hal)
    print("-" * 30)

    # 2. 配置调度任务 (保持不变, 传device_manager)
    print("Main Controller: 配置调度任务...")
    # ... (调度任务配置代码与上一步相同) ...
    schedule.every().day.at("19:00").do(functools.partial(set_device_task, device_manager, "light_livingroom", "on"))
    schedule.every().day.at("07:30").do(functools.partial(set_device_task, device_manager, "light_livingroom", "off"))
    schedule.every(5).minutes.do(functools.partial(read_sensor_task, device_manager, "sensor_temp_main"))
    schedule.every(10).seconds.do(
         functools.partial(lambda dm: dm.set_device_state("light_bedroom", "on" if dm.get_device_state("light_bedroom")['state'] == 'off' else 'off'), device_manager)
    )
    print("  - 任务配置完成。")
    print("-" * 30)

    # 3. 启动调度器线程 (传递 stop_event)
    scheduler_thread = threading.Thread(target=run_scheduler, args=(stop_event,), daemon=True)
    scheduler_thread.start()
    print("Main Controller: 调度器线程已启动。")
    print("-" * 30)

    # 4. 启动网络服务器线程 (保持不变)
    server = ThreadingTCPServerWithManager((HOST, PORT), SmartHomeControllerTCPHandler, device_manager)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Network Server: 服务器已在 {HOST}:{PORT} 启动并监听...")
    print("-" * 30)

    # 5. 启动 CLI 线程 (传递 device_manager 和 stop_event)
    # CLI 不应是守护线程，否则主线程退出时它可能被强制终止，无法完成清理或保存操作
    cli_thread = threading.Thread(target=run_cli, args=(device_manager, stop_event))
    cli_thread.start()
    print("Main Controller: CLI 线程已启动。")
    print("-" * 30)


    # 6. 主线程等待退出信号
    print("Main Controller: 主线程现在将等待退出信号 (来自 CLI 或 Ctrl+C)...")
    try:
        # 等待 stop_event 被设置，或者等待 CLI 线程结束
        # cli_thread.join() # 等待CLI线程自然结束 (当用户输入exit或Ctrl+D/C时)
        # 或者更主动地等待 stop_event
        while not stop_event.is_set():
            # 检查CLI线程是否意外终止 (可选)
            if not cli_thread.is_alive() and not stop_event.is_set():
                 print("Main Controller Warning: CLI 线程意外终止！正在触发关闭...")
                 stop_event.set()
                 break
            time.sleep(0.5) # 短暂休眠，避免CPU空转

        # 一旦 stop_event 被设置 (来自CLI的exit或Ctrl+C)
        print("\nMain Controller: 检测到退出信号，正在执行关闭流程...")

    except KeyboardInterrupt:
        print("\nMain Controller: 在主线程检测到 Ctrl+C，正在关闭...")
        stop_event.set() # 确保停止事件被设置

    # --- 关闭流程 ---
    # 1. 停止调度器 (如果它还没停止)
    if scheduler_thread.is_alive():
        print("Main Controller: 正在停止调度器...")
        schedule.clear()
        # stop_event 应该已经通知了调度器线程，等待它结束
        scheduler_thread.join(timeout=2) # 等待最多2秒
        if scheduler_thread.is_alive():
             print("Main Controller Warning: 调度器线程未能及时停止。")

    # 2. 关闭网络服务器
    print("Main Controller: 正在关闭网络服务器...")
    server.shutdown()
    server.server_close()
    # server_thread 是守护线程，会随主线程退出；或者等待它结束
    # server_thread.join(timeout=2)

    # 3. 等待 CLI 线程结束 (如果它还没结束)
    if cli_thread.is_alive():
        print("Main Controller: 正在等待 CLI 线程退出...")
        # CLI 线程的循环应该在 stop_event 设置后自然退出
        cli_thread.join(timeout=5) # 等待最多5秒
        if cli_thread.is_alive():
             print("Main Controller Warning: CLI 线程未能及时停止 (可能卡在input?)。")


    print("Main Controller: 服务已停止。程序结束。")
    sys.exit(0)