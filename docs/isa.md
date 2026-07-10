# ISA v2 指令集参考

> 三言虚拟机（VM）的 65 个操作码（opcode）。所有后端共享此指令集。

## 字节码格式

```
字节   | 字段          | 说明
------|--------------|------------------
0-3   | MAGIC "SAN0"  | 文件标识
4     | VERSION       | 版本号 (1)
5     | VAR_COUNT     | 全局变量数量
6-9   | CODE_SIZE     | 代码段长度 (4B LE)
10-   | CODE          | 字节码指令流
...   | EXPORT_COUNT  | 导出数量 (2B LE)
...   | EXPORTS[]     | 导出表
```

## 操作码表

### 栈操作 (0x01–0x3E)

| opcode | 代码 | 说明 |
|--------|------|------|
| PUSH_I | 0x01 | 推入立即数 (4B signed LE) |
| PUSH_STR | 0x2D | 推入字符串 (len(2B)+UTF-8) |
| PUSH_FLOAT | 0x48 | 推入浮点数 (8B IEEE 754) |
| LOAD | 0x07 | 加载变量 (1B index) |
| STORE | 0x08 | 存储变量 (1B index) |
| LOAD16 | 0x3B | 2 字节变量索引 |
| STORE16 | 0x3C | 2 字节变量索引 |
| PRINT | 0x0E | 打印栈顶值 |
| CLOSURE | 0x4B | 创建闭包 |

### 控制流 (0x09–0x4C)

| opcode | 代码 | 说明 |
|--------|------|------|
| JMP | 0x09 | 无条件跳转 (2B offset) |
| JMP32 | 0x33 | 32 位跳转 (4B offset) |
| JZ | 0x0A | 栈顶 ≤0 跳转 |
| JNZ | 0x0B | 栈顶 >0 跳转 |
| CALL | 0x0C | 函数调用 (2B addr) |
| CALL32 | 0x3D | 函数调用 (4B addr) |
| RET | 0x0D | 返回 |
| CALL_CLOSURE | 0x4C | 调用闭包 |
| HALT | 0xFF | 停止 |

### 算术 (0x02–0x06)

| opcode | 代码 |
|--------|------|
| ADD | 0x02 |
| SUB | 0x03 |
| MUL | 0x04 |
| DIV | 0x05 |
| MOD | 0x06 |

### 比较 (0x11–0x16)

三值逻辑：真=1，假=-1。

| opcode | 代码 |
|--------|------|
| EQ | 0x11 |
| NE | 0x12 |
| GT | 0x13 |
| LT | 0x14 |
| GTE | 0x15 |
| LTE | 0x16 |

### 逻辑 (0x17, 0x34–0x35)

Kleene 三值逻辑：AND=min(信度)，OR=max(信度)。

| opcode | 代码 |
|--------|------|
| NOT | 0x17 |
| AND | 0x35 |
| OR | 0x34 |

### 位运算 (0x4D–0x59)

| opcode | 代码 | 说明 |
|--------|------|------|
| BIT_AND | 0x4D | 按位与 |
| BIT_OR | 0x4E | 按位或 |
| BIT_XOR | 0x4F | 按位异或 |
| BIT_NOT | 0x50 | 按位非 |
| SHIFT_L | 0x51 | 左移 |
| SHIFT_R | 0x52 | 右移 |
| LO_BYTE | 0x57 | 取低位字节 |
| HI_BYTE | 0x58 | 取高位字节 |
| MRG_BYT | 0x59 | 合并字节 |

### 字符串 (0x19–0x1C)

| opcode | 代码 | 说明 |
|--------|------|------|
| CONCAT | 0x19 | 连接 |
| STRLEN | 0x1A | 长度 |
| STRSUB | 0x1B | 子串 |
| STREQ | 0x1C | 相等 |

### 容器 (0x25–0x2A)

| opcode | 代码 | 说明 |
|--------|------|------|
| GET | 0x25 | 列表取 |
| SET | 0x26 | 列表设 |
| LIST_NEW | 0x27 | 新建列表 |
| LIST_CONCAT | 0x28 | 列表连接 |
| SLICE | 0x29 | 切片 |
| LIST_LEN | 0x2A | 列表长度 |

### 字典 (0x1D–0x21, 0x32)

| opcode | 代码 | 说明 |
|--------|------|------|
| DICT | 0x1D | 新建字典 |
| DICT_GET | 0x1E | 取键 |
| DICT_SET | 0x1F | 置键 |
| DICT_HAS | 0x20 | 含键 |
| DICT_LEN | 0x21 | 字典长度 |
| DICT_KEYS | 0x32 | 键列表 |

### 模块 (0x2E–0x2F)

| opcode | 代码 | 说明 |
|--------|------|------|
| IMPORT | 0x2E | 导入 |
| CALL_EXT | 0x2F | 调用导出函数 |

### IO / 文件 (0x0F–0x10, 0x18, 0x2B–0x2C)

| opcode | 代码 | 说明 |
|--------|------|------|
| IO_READ | 0x0F | 设备读取 |
| IO_WRITE | 0x10 | 设备写入 |
| WAIT | 0x18 | 等待 (ms) |
| READ_FILE | 0x2B | 读文件 |
| WRITE_FILE | 0x2C | 写文件 |

### 类型检查 (0x2F–0x31)

| opcode | 代码 | 说明 |
|--------|------|------|
| IS_NUM | 0x30 | 是数字 |
| IS_STR | 0x31 | 是字符串 |
| IS_LIST | 0x32 | 是列表 |
| SAME | 0x33 | 同一对象 |

## 工具

```bash
# 汇编: .sasm → .bin
python asm.py program.sasm -o program.bin

# 反汇编: .bin → 文本
python disasm.py program.bin --hex
python disasm.py program.bin --export

# 验证: 字节码边界检查
python verify.py program.bin
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `compiler/asm.py` | 汇编器 |
| `compiler/disasm.py` | 反汇编器 |
| `compiler/sanyancc.py` | 交叉编译器 |
| `vm/__init__.py` | Python VM |
| `docs/bootstrap.md` | 自举链 |
