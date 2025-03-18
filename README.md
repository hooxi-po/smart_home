# 智能家居控制器（基于Python）

## 项目简介

本项目是一个基于 Python 的智能家居控制器，旨在模拟和实现一个简单的智能家居系统。它通过虚拟设备驱动、多任务调度、通信机制、异常处理和 Web 用户界面等模块，实现了对虚拟设备的控制和监控。

## 项目特性

* **虚拟设备驱动：** 使用文件 I/O 模拟 Linux 字符设备驱动，无需实际硬件。
* **多任务调度：** 利用线程池和 `schedule` 库实现定时任务和并发处理。
* **通信机制：** 通过 Socket 实现外部控制，队列用于内部数据共享。
* **异常处理：** 使用信号处理实现任务超时控制。
* **Web 用户界面：** 利用 Flask 提供 Web 控制和状态展示。

## 依赖安装

在运行项目之前，请确保已安装以下依赖：

```bash
pip3 install flask schedule
```

## 运行项目

1.  **创建虚拟设备文件：**

    ```bash
    mkdir -p ./virtual_devices
    touch ./virtual_devices/sensor_temp
    touch ./virtual_devices/light_ctl
    ```

2.  **运行主程序：**

    ```bash
    python3 smart_home_controller.py
    ```

3.  **访问 Web 界面：**

    在浏览器中打开 `http://<IP>:5000`，其中 `<IP>` 是运行脚本的设备的 IP 地址。

## 项目结构

```
smart_home/
├── virtual_devices/
│   ├── sensor_temp
│   └── light_ctl
├── smart_home_controller.py
└── README.md
```

## 使用说明

* **Web 控制：** 通过 Web 界面上的按钮控制灯光。
* **状态监控：** 在 Web 界面上查看温度和灯光状态。
* **模拟设备数据：** 使用以下命令模拟传感器数据：

    ```bash
    echo "28.5" > ./virtual_devices/sensor_temp
    cat ./virtual_devices/light_ctl
    ```

## 贡献

欢迎提交 issue 和 pull request，共同完善本项目。

## 许可证

本项目采用 MIT 许可证，详情请见 [LICENSE](LICENSE) 文件。
```

**如何使用：**

1.  **复制内容：** 将上述内容复制到一个名为 `README.md` 的文件中。
2.  **替换 `<IP>`：** 将 `http://<IP>:5000` 中的 `<IP>` 替换为实际的 IP 地址。
3.  **添加许可证：** 如果需要，创建一个 `LICENSE` 文件，并将许可证文本添加到其中。
4.  **放置在项目根目录：** 将 `README.md` 文件放在项目的根目录下。

这个 `README.md` 文件提供了项目的基本信息、安装和使用说明，以及项目结构和贡献方式等，方便其他开发者了解和使用你的项目。
