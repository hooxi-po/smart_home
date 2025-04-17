# 嵌入式智能家居控制器模拟项目 (Smart Home Controller Simulation)

本项目是一个基于 Linux 的嵌入式智能家居控制器的模拟实现，旨在演示如何结合 Linux 内核驱动程序和用户空间应用程序来管理和控制模拟的智能家居设备。

**当前时间:** 2025年4月17日 星期四 22:12:26 (GMT+08:00)
**位置:** Singapore, Singapore

**核心功能:**

* **设备驱动:** 实现了一个 Linux 字符设备驱动 (`smart_device_driver.c`)，模拟多种智能设备。
* **设备管理:** 通过硬件抽象层 (`hal_actual.py`) 和设备管理器 (`device_manager.py`) 统一管理设备。
* **多线程并发:** 使用 Python 的 `threading` 模块实现控制器核心功能（任务调度、网络服务、命令行界面）的并发执行。
* **任务调度:** 使用 `schedule` 库实现定时任务（例如定时开关灯、定时读取传感器）。
* **网络通信:** 提供一个基于 TCP Socket 的服务器 (`main_controller.py`)，允许外部客户端通过 JSON 格式的命令远程控制设备和获取状态。
* **命令行界面 (CLI):** 提供一个交互式命令行界面 (`main_controller.py`)，用于手动控制设备和查看状态。
* **同步机制:** 使用 C 驱动中的 `mutex` 保护设备状态，使用 Python 中的 `Semaphore` 控制对硬件抽象层的并发访问。
* **异常处理:** 包含基本的错误处理（如设备文件访问错误、网络连接错误）和通过信号 (SIGINT, SIGTERM) 实现的优雅关停机制。

## 架构概述

本项目采用分层架构：

1.  **内核层 (Kernel Layer):**
    * `smart_device_driver.c`: Linux 字符设备驱动程序。负责与“硬件”（模拟）交互，创建设备节点 (`/dev/smart_*`)，并向用户空间提供读/写接口。管理设备内部状态（如灯的开关、传感器的模拟值），并使用 `mutex` 进行内部同步。

2.  **硬件抽象层 (HAL - Hardware Abstraction Layer):**
    * `hal_actual.py`: Python 模块。封装了对内核驱动程序提供的设备文件 (`/dev/smart_*`) 的底层访问（`open`, `read`, `write`）。处理文件操作可能出现的异常（如权限、文件不存在）。

3.  **设备管理层 (Device Management Layer):**
    * `device_manager.py`: Python 模块。负责管理所有已知的智能设备。它使用 HAL 与设备驱动交互，维护设备列表，提供更高级、统一的设备操作接口（获取状态、设置状态）给上层应用。使用 `Semaphore` 限制对 HAL 的并发访问。

4.  **应用逻辑层 (Application Logic Layer):**
    * `main_controller.py`: Python 主程序。包含控制器的核心逻辑：
        * **任务调度器:** 使用 `schedule` 库在单独线程中运行定时任务。
        * **网络服务器:** 使用 `socketserver.ThreadingTCPServer` 在单独线程中监听网络端口，处理来自外部客户端的 JSON 命令。
        * **命令行界面 (CLI):** 在单独线程中运行，提供交互式控制。
        * **主线程:** 初始化所有组件，启动各个功能线程，并等待退出信号（通过 `threading.Event` 和 `signal` 模块处理 SIGINT/SIGTERM）以实现优雅关停。

## 文件结构

```
smart_home/
├── Makefile                     # 用于编译 C 驱动程序
├── smart_device_driver.c        # Linux 字符设备驱动源代码
├── smart_device_driver.ko       # (编译后生成) 内核模块文件
├── smart_device_driver.mod.c    # (编译后生成) 模块元数据 C 文件
├── hal_actual.py                # 硬件抽象层 (与实际驱动交互)
├── device_manager.py            # 设备管理器
├── main_controller.py           # 主控制器程序 (调度器, 网络服务器, CLI)
└── README.md                    # 本文件
```

## 先决条件

* **操作系统:** Linux (推荐 Ubuntu, Debian, CentOS 等)
* **编译环境:**
    * `gcc` (用于编译 C 驱动)
    * `make` (用于执行 Makefile)
    * `linux-headers` (对应你的内核版本，编译内核模块需要)
        * 在 Ubuntu/Debian 上: `sudo apt update && sudo apt install build-essential linux-headers-$(uname -r)`
        * 在 CentOS 上: `sudo yum update && sudo yum groupinstall "Development Tools" && sudo yum install kernel-devel`
* **Python 环境:**
    * Python 3.x (推荐 Python 3.6 或更高版本)
    * `pip` (Python 包管理器)
* **Python 依赖库:**
    * `schedule`: 用于任务调度 (`pip install schedule`)
* **权限:** 需要 `sudo` 或 `root` 权限来加载/卸载内核模块 (`insmod`, `rmmod`) 和修改设备文件权限 (`chmod`)。

## 安装与设置

**1. 编译并加载内核驱动程序:**

   * 打开终端，导航到 `smart_home` 目录。
   * **编译驱动:**
      ```bash
      make
      ```
      这会使用 `Makefile` 编译 `smart_device_driver.c`，生成 `smart_device_driver.ko` 文件。
   * **加载驱动模块:**
      ```bash
      sudo insmod smart_device_driver.ko
      ```
   * **验证驱动加载:**
      ```bash
      lsmod | grep smart_device_driver
      ```
      如果看到 `smart_device_driver`，表示加载成功。
   * **检查设备节点:**
      ```bash
      ls /dev/smart_*
      ```
      你应该能看到类似 `/dev/light_livingroom`, `/dev/light_bedroom`, `/dev/socket_kitchen`, `/dev/sensor_temp_main` 的设备文件。
   * **设置设备文件权限:** 为了让 Python 程序（通常以非 root 用户运行）能够读写这些设备文件，需要修改它们的权限。最简单的方式是授予所有用户读写权限（**注意：这在生产环境中可能不安全，仅适用于模拟和测试**）：
      ```bash
      sudo chmod 666 /dev/smart_*
      ```
      或者，你可以将运行 Python 程序的用户添加到拥有这些设备文件的组（通常是 `root` 或 `dialout`，取决于系统配置），并设置组合适的权限。

**2. 准备 Python 应用程序:**

   * 确保你已经安装了 Python 3 和 pip。
   * **安装依赖库:**
      ```bash
      pip install schedule
      ```
   * **检查配置 (可选):**
      * 打开 `main_controller.py`，确认 `DEVICE_CONFIG` 字典中的设备名称和类型与 `smart_device_driver.c` 中的 `initialize_devices` 函数定义一致。默认情况下它们是一致的。
      * 确认网络服务器的 `HOST` 和 `PORT` (默认为 `localhost` 和 `9998`) 是否符合你的需求。

## 使用方法

**1. 运行控制器:**

   * 在 `smart_home` 目录下，运行主控制器脚本：
      ```bash
      python3 main_controller.py
      ```
      *注意：如果之前没有使用 `sudo chmod 666 /dev/smart_*` 全局修改设备权限，你可能需要使用 `sudo python3 main_controller.py` 来运行，以便程序有权限访问 `/dev/smart_*` 文件。但推荐先修改权限，然后用普通用户运行。*

   * 控制器启动后，你会看到初始化信息，并且调度器、网络服务器和 CLI 线程会开始运行。

**2. 使用命令行界面 (CLI):**

   * 控制器运行时，终端会显示 `Controller> ` 提示符。
   * 输入以下命令进行交互：
      * `help`: 显示可用命令列表。
      * `list`: 列出所有已知的设备及其类型。
      * `status all`: 显示所有设备当前的状态和最后更新时间。
      * `status <device_id>`: 显示指定设备的状态。例如: `status light_livingroom`。
      * `open <device_id>`: 打开（设置为 "on"）指定的设备（仅适用于灯和插座）。例如: `open light_bedroom`。
      * `close <device_id>`: 关闭（设置为 "off"）指定的设备（仅适用于灯和插座）。例如: `close socket_kitchen`。
      * `set <device_id> <state>`: 直接设置设备状态（谨慎使用）。例如: `set light_livingroom on`。
      * `exit` 或 `quit`: 关闭控制器。

**3. 使用网络接口 (TCP Socket):**

   * 网络服务器默认监听在 `localhost:9998`。
   * 你可以使用任何 TCP 客户端（如 `netcat`, `telnet`，或编写一个简单的 Python 客户端）连接到该地址和端口。
   * 通信协议基于 JSON：
      * **客户端请求 (发送给控制器):**
         ```json
         {
           "command": "<command_name>",
           "device_id": "<target_device_id>", // set, get 需要
           "state": "<target_state>"          // set 需要
         }
         ```
      * **服务器响应 (控制器返回给客户端):**
         ```json
         {
           "success": true/false,
           "data": { ... },      // 成功时返回的数据 (get, status_all, list_devices)
           "message": "...",     // 成功时的附加信息 (set, ping)
           "error": "..."        // 失败时的错误信息
         }
         ```
   * **支持的命令 (`command_name`):**
      * `set`: 设置设备状态。
         * 请求: `{"command": "set", "device_id": "light_livingroom", "state": "on"}`
         * 响应 (成功): `{"success": true, "message": "设备 light_livingroom 设置为 on"}`
         * 响应 (失败): `{"success": false, "error": "设置设备 light_livingroom 失败"}`
      * `get`: 获取单个设备状态。
         * 请求: `{"command": "get", "device_id": "sensor_temp_main"}`
         * 响应 (成功): `{"success": true, "data": {"state": 23.1, "last_updated": 1713363146.123}}`
         * 响应 (失败): `{"success": false, "error": "设备 sensor_temp_main 未找到或获取失败"}`
      * `status_all`: 获取所有设备状态。
         * 请求: `{"command": "status_all"}`
         * 响应: `{"success": true, "data": {"light_livingroom": {"state": "off", ...}, "sensor_temp_main": {"state": 23.1, ...}}}`
      * `list_devices`: 列出所有已知设备。
         * 请求: `{"command": "list_devices"}`
         * 响应: `{"success": true, "data": {"light_livingroom": "light", "light_bedroom": "light", ...}}`
      * `ping`: 测试连接。
         * 请求: `{"command": "ping"}`
         * 响应: `{"success": true, "message": "pong"}`

   * **使用 `netcat` (nc) 测试示例:**
      ```bash
      # 发送 get 命令
      echo '{"command": "get", "device_id": "light_livingroom"}' | nc localhost 9998

      # 发送 set 命令
      echo '{"command": "set", "device_id": "light_livingroom", "state": "on"}' | nc localhost 9998
      ```

**4. 停止控制器:**

   * 在 CLI 中输入 `exit` 或 `quit`。
   * 在运行控制器的终端按 `Ctrl+C` (会触发 SIGINT 信号)。
   * 使用 `kill <pid>` 命令发送 SIGTERM 信号。
   * 控制器会尝试优雅地关闭所有线程。

**5. 卸载驱动程序:**

   * 当你不再需要控制器时，可以卸载内核模块：
      ```bash
      sudo rmmod smart_device_driver
      ```
   * 验证卸载：
      ```bash
      lsmod | grep smart_device_driver
      ```
      此时应该没有输出。

## 技术细节

* **驱动 (`smart_device_driver.c`):**
    * 使用标准字符设备接口 (`file_operations`)。
    * 动态分配主设备号 (`alloc_chrdev_region`)。
    * 使用 `class_create` 和 `device_create` 在 `/sys/class` 和 `/dev` 下创建条目。
    * 内部维护 `smart_device` 结构体数组，每个代表一个设备实例。
    * `read` 操作：对灯/插座返回 "on"/"off" 字符串；对温度传感器，会调用 `simulate_sensor_update` 产生一个略微随机变化的值（在 10.0 到 35.0 之间），然后返回字符串形式的浮点数。
    * `write` 操作：仅对灯/插座有效，接受 "on", "off", "1", "0" 字符串，更新内部状态。对传感器写入返回 `-EPERM`。
    * 使用 `mutex_lock_interruptible` 和 `mutex_unlock` 保护对每个设备 `state` 的访问。
* **硬件抽象层 (`hal_actual.py`):**
    * 通过 `open()`, `read()`, `write()` 与 `/dev/smart_*` 文件交互。
    * 处理 `FileNotFoundError`, `PermissionError`, `OSError`，转换为 `DeviceConfigurationError`。
    * 对传感器读取的值尝试转换为 `float`。
    * 写入时将布尔值或 "0"/"1" 转换为驱动期望的 "on"/"off"。
* **设备管理器 (`device_manager.py`):**
    * 持有 `ActualHAL` 实例。
    * `get_device_state`/`set_device_state` 调用 HAL 的对应方法。
    * 使用 `threading.Semaphore(1)` (`_access_semaphore`) 保证同一时间只有一个线程通过 `DeviceManager` 访问 `ActualHAL`，避免了对驱动调用的潜在竞争（虽然驱动本身有 `mutex` 保护，但 Python 层的信号量提供了更上层的串行化访问控制）。
* **主控制器 (`main_controller.py`):**
    * **Threading:**
        * `scheduler_thread`: 运行 `run_scheduler`，循环调用 `schedule.run_pending()`。
        * `server_thread`: 运行 `server.serve_forever()`，`ThreadingTCPServer` 会为每个连接创建一个新线程执行 `SmartHomeControllerTCPHandler`。
        * `cli_thread`: 运行 `run_cli`，处理用户输入。
        * `stop_event` (`threading.Event`): 用于协调所有线程的关闭。当需要退出时（CLI 输入 `exit`、收到 SIGINT/SIGTERM），该事件被设置，各线程循环检测到后退出。
    * **Scheduling:** 使用 `schedule` 库定义各种定时规则（每天特定时间、每隔 N 秒）。
    * **Networking:** `socketserver.ThreadingTCPServer` + `BaseRequestHandler` 实现多线程 TCP 服务器。JSON 用于数据序列化。包含对常见网络错误的捕获。
    * **Signal Handling:** `signal.signal(signal.SIGINT, ...)` 和 `signal.signal(signal.SIGTERM, ...)` 捕获中断和终止信号，调用 `handle_signal` 设置 `stop_event`。
* **同步:**
    * 内核态：每个 C 设备结构体内的 `mutex` 保护自身状态。
    * 用户态：`DeviceManager` 的 `Semaphore(1)` 保证对 HAL 的串行访问。
* **配置:** 设备列表和类型在 C 驱动和 Python 控制器 (`DEVICE_CONFIG`) 中都需要定义，并且必须匹配。网络端口在 `main_controller.py` 中定义。

## 局限性与已知问题

* **纯模拟:** 本项目完全基于模拟，没有与真实硬件交互。驱动程序模拟设备行为，包括传感器的随机读数。
* **无状态持久化:** 设备状态仅存在于驱动程序的内存中（或由驱动模拟）。当驱动卸载或控制器重启时，所有状态（如灯是开是关）将丢失，并恢复到驱动代码中定义的初始状态。
* **有限的错误处理:** 虽然处理了基本的设备访问和网络错误，但没有实现任务执行超时监控和通过信号进行内部错误上报等高级功能。
* **安全性:** 网络接口没有任何认证或加密，任何能访问该端口的客户端都可以控制设备，极不安全，仅适用于本地测试。
* **未完全遵循原始需求文档:**
    * 未使用明确的 Pipe, Message Queue 或 Shared Memory 进行 Python 内部线程通信。
    * 未使用通用线程池管理任务。
    * 未使用信号机制处理任务超时或内部错误通知。

## 未来可能的改进方向

* 集成真实硬件接口（GPIO, I2C, SPI 等）。
* 添加状态持久化（如保存到文件或数据库）。
* 实现更健壮的错误处理和恢复机制。
* 实现任务执行超时监控。
* 为网络接口添加认证和加密（如 TLS/SSL）。
* 开发图形用户界面 (GUI) 或 Web 界面。
* 支持更多类型的智能设备。
* 使用消息队列（如 RabbitMQ, ZeroMQ）或共享内存进行更明确的内部通信。
* 引入数据库存储设备信息和历史数据。


## 作者

刘剑涛

```