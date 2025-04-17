#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>       // file_operations
#include <linux/cdev.h>     // cdev_init, cdev_add, cdev_del
#include <linux/device.h>   // class_create, device_create
#include <linux/uaccess.h>  // copy_to_user, copy_from_user
#include <linux/slab.h>     // kmalloc, kfree
#include <linux/mutex.h>    // Mutex for synchronization
#include <linux/random.h>   // For simulating sensor changes

#define DRIVER_NAME "smart_home_dev"
#define MAX_DEVICES 4 // 定义支持的最大设备数量

// --- 设备类型 ---
typedef enum {
    DEV_TYPE_LIGHT,
    DEV_TYPE_SOCKET,
    DEV_TYPE_SENSOR_TEMP,
    // 可以添加更多类型
} device_type_t;

// --- 设备状态 ---
// 使用联合体节省空间，虽然在这个简单例子中影响不大
typedef union {
    char switch_state[4]; // "on" or "off"
    char sensor_value[10]; // e.g., "23.5", "-5.2"
} device_state_t;

// --- 每个设备的结构体 ---
struct smart_device {
    const char *name;       // 设备名称 (e.g., "light_livingroom")
    device_type_t type;     // 设备类型
    struct cdev cdev;       // 字符设备结构
    dev_t dev_num;          // 设备号 (主次设备号)
    struct device *device;  // 内核设备模型使用的设备结构
    struct mutex lock;      // 用于保护设备状态的互斥锁
    device_state_t state;   // 当前设备状态 (模拟值)
};

// --- 全局变量 ---
static struct smart_device smart_devices[MAX_DEVICES];
static int major_number;
static struct class *smart_home_class = NULL;
static int device_count = 0; // 当前已注册的设备数量

// --- 模拟设备定义 ---
// 在这里定义我们想要模拟的设备
static void initialize_devices(void) {
    // 设备 1: 客厅灯
    smart_devices[0].name = "light_livingroom";
    smart_devices[0].type = DEV_TYPE_LIGHT;
    strncpy(smart_devices[0].state.switch_state, "off", sizeof(smart_devices[0].state.switch_state) - 1);
    device_count++;

    // 设备 2: 卧室灯
    smart_devices[1].name = "light_bedroom";
    smart_devices[1].type = DEV_TYPE_LIGHT;
    strncpy(smart_devices[1].state.switch_state, "off", sizeof(smart_devices[1].state.switch_state) - 1);
    device_count++;

    // 设备 3: 厨房插座
    smart_devices[2].name = "socket_kitchen";
    smart_devices[2].type = DEV_TYPE_SOCKET;
    strncpy(smart_devices[2].state.switch_state, "off", sizeof(smart_devices[2].state.switch_state) - 1);
    device_count++;

    // 设备 4: 主温度传感器
    smart_devices[3].name = "sensor_temp_main";
    smart_devices[3].type = DEV_TYPE_SENSOR_TEMP;
    strncpy(smart_devices[3].state.sensor_value, "22.5", sizeof(smart_devices[3].state.sensor_value) - 1);
    device_count++;

    // 注意：确保 MAX_DEVICES 足够大
}

// --- 文件操作函数实现 ---

static int smart_dev_open(struct inode *inode, struct file *file) {
    // 从 inode 获取设备结构体指针
    struct smart_device *dev = container_of(inode->i_cdev, struct smart_device, cdev);
    file->private_data = dev; // 将设备结构体指针存入 file->private_data

    // 可以增加引用计数等操作，这里简化
    pr_info("%s: Device '%s' opened.\n", DRIVER_NAME, dev->name);
    return 0;
}

static int smart_dev_release(struct inode *inode, struct file *file) {
    struct smart_device *dev = file->private_data;
    // 可以减少引用计数等操作，这里简化
    pr_info("%s: Device '%s' closed.\n", DRIVER_NAME, dev->name);
    return 0;
}

// 模拟传感器读数变化
static void simulate_sensor_update(struct smart_device *dev) {
    int temp_int, temp_frac;
    long current_temp_scaled;
    long change;

    // 仅处理温度传感器
    if (dev->type != DEV_TYPE_SENSOR_TEMP) {
        return;
    }

    // 将当前字符串值转换为整数（乘以10）
    if (sscanf(dev->state.sensor_value, "%d.%d", &temp_int, &temp_frac) == 2) {
         current_temp_scaled = temp_int * 10 + (temp_int >= 0 ? temp_frac : -temp_frac);
    } else if (sscanf(dev->state.sensor_value, "%d", &temp_int) == 1) {
         current_temp_scaled = temp_int * 10;
         temp_frac = 0; // Ensure frac part is 0 if only int part is read
    }
     else {
        pr_warn("%s: Could not parse sensor value '%s' for %s\n", DRIVER_NAME, dev->state.sensor_value, dev->name);
        current_temp_scaled = 200; // Default to 20.0 C
    }


    // 随机变化 (-0.2 到 +0.2 度，即 -2 到 +2 乘以10)
    get_random_bytes(&change, sizeof(change));
    change = (change % 5) - 2; // Generates -2, -1, 0, 1, 2
    current_temp_scaled += change;

    // 限制在合理范围 (10.0 到 35.0 度)
    if (current_temp_scaled < 100) current_temp_scaled = 100;
    if (current_temp_scaled > 350) current_temp_scaled = 350;

    // 格式化回字符串
    temp_int = current_temp_scaled / 10;
    temp_frac = abs(current_temp_scaled % 10); // Use abs for fractional part
    snprintf(dev->state.sensor_value, sizeof(dev->state.sensor_value), "%d.%d", temp_int, temp_frac);
}


static ssize_t smart_dev_read(struct file *file, char __user *user_buf, size_t count, loff_t *offset) {
    struct smart_device *dev = file->private_data;
    char *read_data;
    size_t data_len;
    ssize_t retval;

    // 获取设备锁
    if (mutex_lock_interruptible(&dev->lock)) {
        return -ERESTARTSYS;
    }

    // 根据设备类型确定要读取的数据
    if (dev->type == DEV_TYPE_LIGHT || dev->type == DEV_TYPE_SOCKET) {
        read_data = dev->state.switch_state;
        data_len = strlen(read_data);
    } else if (dev->type == DEV_TYPE_SENSOR_TEMP) {
        // 模拟传感器读数变化
        simulate_sensor_update(dev);
        read_data = dev->state.sensor_value;
        data_len = strlen(read_data);
    } else {
        pr_warn("%s: Read attempted on unsupported device type for %s\n", DRIVER_NAME, dev->name);
        mutex_unlock(&dev->lock);
        return -EINVAL;
    }

    // 检查偏移量，简单驱动只支持从头读取
    if (*offset >= data_len) {
        mutex_unlock(&dev->lock);
        return 0; // End of file
    }

    // 确保不会读取超过数据长度或用户缓冲区大小
    if (count > data_len - *offset) {
        count = data_len - *offset;
    }

    // 将内核数据拷贝到用户空间
    if (copy_to_user(user_buf, read_data + *offset, count)) {
        pr_err("%s: Failed to copy data to user space for %s\n", DRIVER_NAME, dev->name);
        retval = -EFAULT;
    } else {
        pr_info("%s: Read %zu bytes from %s: '%s'\n", DRIVER_NAME, count, dev->name, read_data);
        *offset += count; // 更新偏移量
        retval = count;    // 返回读取的字节数
    }

    // 释放锁
    mutex_unlock(&dev->lock);
    return retval;
}

static ssize_t smart_dev_write(struct file *file, const char __user *user_buf, size_t count, loff_t *offset) {
    struct smart_device *dev = file->private_data;
    char kbuf[16]; // 内核缓冲区，用于存放来自用户空间的数据
    size_t buf_size = sizeof(kbuf) - 1;
    ssize_t retval;

    // 只允许写入灯和插座类型设备
    if (dev->type != DEV_TYPE_LIGHT && dev->type != DEV_TYPE_SOCKET) {
        pr_warn("%s: Write attempted on read-only device %s (type: %d)\n", DRIVER_NAME, dev->name, dev->type);
        return -EPERM; // Operation not permitted
    }

    // 获取设备锁
    if (mutex_lock_interruptible(&dev->lock)) {
        return -ERESTARTSYS;
    }

    // 确保写入数据量不超过缓冲区大小
    if (count > buf_size) {
        count = buf_size;
    }

    // 从用户空间拷贝数据到内核缓冲区
    if (copy_from_user(kbuf, user_buf, count)) {
        pr_err("%s: Failed to copy data from user space for %s\n", DRIVER_NAME, dev->name);
        mutex_unlock(&dev->lock);
        return -EFAULT;
    }
    kbuf[count] = '\0'; // 确保字符串结束

    // 处理写入的数据 (去除可能的换行符)
    if (count > 0 && kbuf[count - 1] == '\n') {
        kbuf[count - 1] = '\0';
    }


    // 检查是否是有效的状态 ("on" 或 "off")
    if (strcmp(kbuf, "on") == 0 || strcmp(kbuf, "1") == 0) {
        strncpy(dev->state.switch_state, "on", sizeof(dev->state.switch_state) - 1);
        retval = count;
        pr_info("%s: Set device %s state to ON\n", DRIVER_NAME, dev->name);
    } else if (strcmp(kbuf, "off") == 0 || strcmp(kbuf, "0") == 0) {
        strncpy(dev->state.switch_state, "off", sizeof(dev->state.switch_state) - 1);
        retval = count;
        pr_info("%s: Set device %s state to OFF\n", DRIVER_NAME, dev->name);
    } else {
        pr_warn("%s: Invalid state '%s' written to device %s\n", DRIVER_NAME, kbuf, dev->name);
        retval = -EINVAL; // Invalid argument
    }

    // 释放锁
    mutex_unlock(&dev->lock);
    return retval;
}

// --- 文件操作结构体 ---
static const struct file_operations smart_dev_fops = {
    .owner = THIS_MODULE,
    .open = smart_dev_open,
    .release = smart_dev_release,
    .read = smart_dev_read,
    .write = smart_dev_write,
};

// --- 模块初始化函数 ---
static int __init smart_home_driver_init(void) {
    int i;
    int result;

    pr_info("%s: Initializing Smart Home Device Driver...\n", DRIVER_NAME);

    // 1. 动态分配主设备号
    result = alloc_chrdev_region(&smart_devices[0].dev_num, 0, MAX_DEVICES, DRIVER_NAME);
    if (result < 0) {
        pr_err("%s: Failed to allocate major number\n", DRIVER_NAME);
        return result;
    }
    major_number = MAJOR(smart_devices[0].dev_num);
    pr_info("%s: Registered correctly with major number %d\n", DRIVER_NAME, major_number);

    // 2. 创建设备类 /sys/class/smart_home_dev/
    smart_home_class = class_create(DRIVER_NAME);
    if (IS_ERR(smart_home_class)) {
        unregister_chrdev_region(smart_devices[0].dev_num, MAX_DEVICES);
        pr_err("%s: Failed to create device class\n", DRIVER_NAME);
        return PTR_ERR(smart_home_class);
    }
    pr_info("%s: Device class created successfully\n", DRIVER_NAME);

    // 3. 初始化模拟设备状态
    initialize_devices();

    // 4. 为每个设备注册 cdev 和创建设备节点
    for (i = 0; i < device_count; i++) {
        // 计算当前设备的设备号
        smart_devices[i].dev_num = MKDEV(major_number, i);

        // 初始化互斥锁
        mutex_init(&smart_devices[i].lock);

        // 初始化 cdev 结构并关联 fops
        cdev_init(&smart_devices[i].cdev, &smart_dev_fops);
        smart_devices[i].cdev.owner = THIS_MODULE;

        // 添加 cdev 到内核
        result = cdev_add(&smart_devices[i].cdev, smart_devices[i].dev_num, 1);
        if (result < 0) {
            pr_err("%s: Failed to add cdev for %s\n", DRIVER_NAME, smart_devices[i].name);
            // 清理已添加的设备
            while (--i >= 0) {
                device_destroy(smart_home_class, smart_devices[i].dev_num);
                cdev_del(&smart_devices[i].cdev);
                 mutex_destroy(&smart_devices[i].lock);
            }
            class_destroy(smart_home_class);
            unregister_chrdev_region(smart_devices[0].dev_num, MAX_DEVICES);
            return result;
        }

        // 创建设备节点 /dev/smart_xxx
        smart_devices[i].device = device_create(smart_home_class, NULL, smart_devices[i].dev_num, NULL, smart_devices[i].name);
        if (IS_ERR(smart_devices[i].device)) {
            pr_err("%s: Failed to create device node for %s\n", DRIVER_NAME, smart_devices[i].name);
            cdev_del(&smart_devices[i].cdev);
             mutex_destroy(&smart_devices[i].lock);
            // 清理已添加的设备
             while (--i >= 0) {
                device_destroy(smart_home_class, smart_devices[i].dev_num);
                cdev_del(&smart_devices[i].cdev);
                 mutex_destroy(&smart_devices[i].lock);
            }
            class_destroy(smart_home_class);
            unregister_chrdev_region(smart_devices[0].dev_num, MAX_DEVICES);
            return PTR_ERR(smart_devices[i].device);
        }
        pr_info("%s: Device node /dev/%s created for %s\n", DRIVER_NAME, smart_devices[i].name, smart_devices[i].name);
    }

    pr_info("%s: Smart Home Device Driver Initialized Successfully.\n", DRIVER_NAME);
    return 0; // Success
}

// --- 模块退出函数 ---
static void __exit smart_home_driver_exit(void) {
    int i;
    pr_info("%s: Exiting Smart Home Device Driver...\n", DRIVER_NAME);

    // 销毁设备节点、删除 cdev、销毁锁
    for (i = 0; i < device_count; i++) {
        device_destroy(smart_home_class, smart_devices[i].dev_num);
        cdev_del(&smart_devices[i].cdev);
         mutex_destroy(&smart_devices[i].lock);
    }

    // 销毁设备类
    class_destroy(smart_home_class);

    // 释放主设备号
    unregister_chrdev_region(MKDEV(major_number, 0), MAX_DEVICES); // Use MKDEV here

    pr_info("%s: Smart Home Device Driver Unloaded.\n", DRIVER_NAME);
}

// --- 模块注册 ---
module_init(smart_home_driver_init);
module_exit(smart_home_driver_exit);

// --- 模块信息 ---
MODULE_LICENSE("GPL");
MODULE_AUTHOR("Your Name");
MODULE_DESCRIPTION("Simple character device driver for simulating smart home devices");
MODULE_VERSION("0.1");