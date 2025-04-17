# If cross-compiling...
# ARCH=arm
# CROSS_COMPILE=arm-linux-gnueabihf-
# KERNEL_DIR ?= /path/to/your/kernel/source/or/headers

# If compiling locally
UNAME_R := $(shell uname -r)
KERNEL_DIR ?= /lib/modules/$(UNAME_R)/build
# Store PWD in a variable as well
MODULE_DIR := $(shell pwd)

obj-m += smart_device_driver.o

.PHONY: all
all:
	# 在变量周围添加引号，特别是 M= 参数
	$(MAKE) -C "$(KERNEL_DIR)" M="$(MODULE_DIR)" modules

.PHONY: clean
clean:
	# 在变量周围添加引号
	$(MAKE) -C "$(KERNEL_DIR)" M="$(MODULE_DIR)" clean
	# Cleanup command
	rm -f modules.order Module.symvers *.ko *.o *.mod.c .*.cmd *.symvers .tmp_versions/ -rf

.PHONY: help
help:
	@echo "Usage:"
	@echo "  make         - Compile the kernel module"
	@echo "  make clean   - Remove compiled files"
	@echo ""
	@echo "After compilation:"
	@echo "  sudo insmod smart_device_driver.ko  - Load the module"
	@echo "  ls /dev/smart_* - Check created device files (adjust permissions if needed, e.g., sudo chmod 666 /dev/smart_*)"
	@echo "  sudo rmmod smart_device_driver    - Unload the module"
	@echo ""
	@echo "To view kernel messages:"
	@echo "  dmesg | tail"