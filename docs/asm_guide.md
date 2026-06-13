# Sanyan 汇编器 — LLM 注意事项

## 值系统

所有栈上值都是 **tagged pointer**：

```
整数 42 → 栈上存 85  (42 << 1 | 1 = 0x55)
整数 0  → 栈上存 1   (0 << 1 | 1 = 0x01)
字符串  → 栈上存指针 (LSB=0)
```

**不要直接比较 raw 值。** 算术运算(ADD/SUB/MUL)会自动 untag、计算、retag。

## JZ / JNZ 陷阱（重要）

JZ 检查 `值 == 0`，JNZ 检查 `值 != 0`。但：

| 栈上值 | JZ 行为 | 原因 |
|--------|---------|------|
| tagged 0 (=1) | **不跳** | 1 ≠ 0 |
| tagged 42 (=85) | **不跳** | 85 ≠ 0 |
| TritValue(-1) | **不跳** | to_int()=-1 ≠ 0 |
| TritValue(0) | **跳** | to_int()=0 |
| TritValue(1) | **不跳** | to_int()=1 ≠ 0 |

**正确用法**：比较后加 1 归一化到 0/2，再用 JZ：

```asm
    GT          ; 推 TritValue(1或-1)
    PUSH_I 1    ; 推 tagged 1
    ADD         ; TritValue+tagged→TritValue: -1+1=0, 1+1=2
    JZ label    ; 值为0时跳 (原始GT结果为-1时)
```

**错误用法**（永远跳不到）：
```asm
    GT
    JZ label    ; TritValue 永远 ≠ 0, 永远不跳
```

## 比较指令返回值

| 指令 | 真 | 假 |
|------|-----|-----|
| GT/LT/EQ/GTE | TritValue(1) | TritValue(-1) |
| IS_NUM/IS_STR/IS_LIST | TritValue(1) | TritValue(-1) |

**所有比较都返回 TritValue，不是 int。** 如果需要 int 0/1 结果，用 `PUSH_I 1; ADD` 转换。

## CALL vs JMP 的区别

| | CALL | JMP/JZ/JNZ |
|------|------|------|
| 操作数 | **绝对地址** | **相对偏移** |
| 例 | `CALL func` → 跳转到 func 的地址 | `JMP loop` → 跳 (当前位置+偏移) |
| RET | 恢复 pc + sp | 不涉及 |

CALL 编码为 3 字节(opcode + 2B address)，JMP 编码为 3 字节(opcode + 2B signed offset)。

## 字符串

```asm
PUSH_STR "你好"    ; 推字符串(UTF-16LE编码)
```

- 最大长度 255 字符 (PUSH_STR) 或 65535 (PUSH_STR16)
- STRSUB 参数是 **字符索引**（UTF-8 字符数，非字节数）

## 递归与调用栈

- 调用栈深度 64 帧（CALL 64 次后静默失败）
- 每帧保存全部变量（VM=256 槽位）
- 递归函数每个调用有独立变量空间

## 常见错误

1. **忘记 STORE**：函数第一行必须 `STORE N` 接收参数
   ```asm
   func:           ; ✗ 忘记 STORE
       LOAD 0      ; 读到的是调用者传入的值还是垃圾?
   ```

   正确：
   ```asm
   func:
       STORE 0     ; 弹出第一个参数到 var[0]
       LOAD 0      ; 现在读回参数
   ```

2. **标签未定义**：所有 JMP/CALL 目标必须已定义标签

3. **栈溢出**：超过 512 个值后 push 静默失败(跳回 dispatch)

4. **变量编号**：STORE 的操作数是变量槽位号(0-255)，不是值

5. **除零**：DIV/MOD 除数为 0 时结果 = 0

## 可用的 LOAD16/STORE16

变量数超过 255 时：
```asm
LOAD16 300     ; 加载 var[300], 3字节编码
STORE16 300    ; 存入 var[300]
```

## 示例程序

### 递归斐波那契
```asm
    PUSH_I 10      ; n = 10
    CALL fib
    PRINT
    HALT

fib:
    STORE 0        ; 接收 n
    LOAD 0         ; n
    PUSH_I 1
    GT             ; n > 1? → TritValue
    PUSH_I 1
    ADD            ; -1→0 或 1→2
    JZ base        ; n ≤ 1 → base
    ; 递归: fib(n-1) + fib(n-2)
    LOAD 0; PUSH_I 1; SUB; CALL fib
    STORE 1        ; 保存 fib(n-1)
    LOAD 0; PUSH_I 2; SUB; CALL fib
    LOAD 1; ADD    ; fib(n-1)+fib(n-2)
    RET
base:
    LOAD 0         ; 返回 n (0 或 1)
    RET
```

### 简单循环
```asm
    PUSH_I 0; STORE 0      ; i = 0
loop:
    LOAD 0; PUSH_I 1; ADD; STORE 0   ; i++
    LOAD 0; PUSH_I 5; LT             ; i < 5?
    PUSH_I 1; ADD; JZ end            ; i>=5 → end
    JMP loop
end:
    LOAD 0; PRINT; HALT
```

### 列表操作
```asm
    PUSH_I 10; PUSH_I 20; PUSH_I 30   ; 元素
    PUSH_I 3                           ; 长度
    LIST_NEW                           ; [10,20,30]
    PUSH_I 1                           ; 索引
    LIST_GET                           ; items[1] = 20
    PRINT
    HALT
```
