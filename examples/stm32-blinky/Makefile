# ── 三言 → STM32 交叉编译（STM32F103 Blue Pill） ──
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
CFLAGS  = -mcpu=cortex-m3 -mthumb -Os -ffreestanding -nostartfiles \
          -DSTM32F103xB -I. -Wall -Wextra
LDFLAGS = -T stm32_flash.ld -nostartfiles -ffreestanding -lgcc

# ── 主机目标（PC 测试用） ──
HOST_CC  = gcc
HOST_OUT = runtime_host

# ── 三言编译器 ──
SAN_CC  = python -X utf8 ../../sanyancc.py

# ── 目标 ──
all: firmware.bin

# 1. 从 .san 编译字节码 → bytecode.bin
bytecode.bin: blinky.san
	$(SAN_CC) blinky.san -o bytecode.bin

# 2. 从 bytecode.bin 生成 C 数组头文件
firmware_data.h: bytecode.bin
	python -X utf8 -c "\
import struct; \
with open('bytecode.bin','rb') as f: data = f.read(); \
magic,ver,varc,sz = struct.unpack_from('<4sBBH',data,0); \
code = data[8:8+sz]; \
lines = ['#ifndef FIRMWARE_DATA_H','#define FIRMWARE_DATA_H','', \
         f'#define FIRMWARE_VARS {varc}', \
         f'#define FIRMWARE_SIZE {len(code)}','', \
         'static const unsigned char firmware_code[FIRMWARE_SIZE] = {']; \
for i in range(0,len(code),12): \
    lines.append('  ' + ', '.join(f'0x{b:02x}' for b in code[i:i+12]) + ','); \
lines.append('};','', '#endif'); \
open('firmware_data.h','w').write('\n'.join(lines) + '\n'); \
print('firmware_data.h regenerated')"

# 3. 编译 STM32 ELF
firmware.elf: runtime_stm32.c firmware_data.h stm32_flash.ld
	$(CC) $(CFLAGS) runtime_stm32.c -o firmware.elf $(LDFLAGS)

# 4. 生成烧录文件（.bin → st-flash）
firmware.bin: firmware.elf
	$(OBJCOPY) -O binary firmware.elf firmware.bin

# 5. 烧录到 STM32
flash: firmware.bin
	st-flash write firmware.bin 0x08000000

# ── PC 上位机测试（需要 gcc，跳过二进制检查） ──
host_test: bytecode.bin
	$(HOST_CC) -o $(HOST_OUT) ../../runtime.c -Wall -Wextra
	./$(HOST_OUT) bytecode.bin

# ── 一键：编译 + 烧录 ──
run: flash

# ── 清理 ──
clean:
	rm -f bytecode.bin firmware.elf firmware.bin firmware_data.h $(HOST_OUT)

.PHONY: all flash host_test run clean
