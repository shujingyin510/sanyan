/**
 * runtime.c — 三言平坦字节码 C 解释器
 * 编译测试: gcc -o runtime runtime.c && ./runtime firmware.bin
 * STM32:   arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os ...
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

/* ── 配置 ────────────────────────────────────────── */
#ifndef VAR_MAX
#define VAR_MAX 64
#endif
#ifndef STACK_MAX
#define STACK_MAX 256
#endif
#ifndef NATIVE_DEV_MAX
#define NATIVE_DEV_MAX 8
#endif

/* ── 指令码（与 sanyancc.py INSTR 对应） ──────── */
typedef enum {
    NOP      = 0x00,
    PUSH_I   = 0x01,
    ADD      = 0x02,
    SUB      = 0x03,
    MUL      = 0x04,
    DIV      = 0x05,
    MOD      = 0x06,
    LOAD     = 0x07,
    STORE    = 0x08,
    JMP      = 0x09,
    JZ       = 0x0A,
    JNZ      = 0x0B,
    CALL     = 0x0C,
    RET      = 0x0D,
    PRINT    = 0x0E,
    IO_READ  = 0x0F,
    IO_WRITE = 0x10,
    EQ       = 0x11,
    NE       = 0x12,
    GT       = 0x13,
    LT       = 0x14,
    GTE      = 0x15,
    LTE      = 0x16,
    NOT      = 0x17,
    WAIT     = 0x18,
    HALT     = 0xFF,
} Opcode;

/* ── VM 状态 ────────────────────────────────────── */
typedef struct {
    int32_t stack[STACK_MAX];
    int16_t sp;               /* 栈顶指针 */
    int32_t vars[VAR_MAX];
    uint8_t var_count;
    const uint8_t *code;
    uint32_t pc;
    int32_t retval;           /* CALL/RET 返回值 */
    uint16_t call_stack[32];
    uint8_t call_depth;
} VM;

/* ── 原生设备回调 ──────────────────────────────── */
typedef int32_t (*native_read_fn)(uint8_t dev_id);
typedef void    (*native_write_fn)(uint8_t dev_id, int32_t val);

typedef struct {
    native_read_fn  read;
    native_write_fn write;
} NativeDevice;

static NativeDevice _devices[NATIVE_DEV_MAX];
static uint8_t _dev_count;

void vm_register_device(uint8_t id, native_read_fn r, native_write_fn w) {
    if (id < NATIVE_DEV_MAX && _dev_count < NATIVE_DEV_MAX) {
        _devices[id] = (NativeDevice){r, w};
        _dev_count++;
    }
}

/* ── 栈操作 ──────────────────────────────────────── */
static inline void push(VM *vm, int32_t v) {
    if (vm->sp >= STACK_MAX) { fprintf(stderr, "栈溢出\n"); exit(1); }
    vm->stack[vm->sp++] = v;
}
static inline int32_t pop(VM *vm) {
    if (vm->sp <= 0) { fprintf(stderr, "栈下溢\n"); exit(1); }
    return vm->stack[--vm->sp];
}
static inline int32_t peek(VM *vm) {
    if (vm->sp <= 0) return 0;
    return vm->stack[vm->sp - 1];
}

/* ── 读取指令操作数 ──────────────────────────────── */
static inline uint8_t read_u8(const uint8_t *code, uint32_t *pc) {
    return code[(*pc)++];
}
static inline int32_t read_i32(const uint8_t *code, uint32_t *pc) {
    int32_t v;
    memcpy(&v, code + *pc, 4);
    *pc += 4;
    return v;
}
static inline int16_t read_i16(const uint8_t *code, uint32_t *pc) {
    int16_t v;
    memcpy(&v, code + *pc, 2);
    *pc += 2;
    return v;
}

/* ── 主解释循环 ────────────────────────────────── */
int vm_run(VM *vm) {
    while (1) {
        uint8_t op = read_u8(vm->code, &vm->pc);
        int32_t a, b, r;

        switch (op) {
        case NOP:
            break;

        case PUSH_I:
            a = read_i32(vm->code, &vm->pc);
            push(vm, a);
            break;

        case ADD:
            b = pop(vm); a = pop(vm);
            push(vm, a + b);
            break;
        case SUB:
            b = pop(vm); a = pop(vm);
            push(vm, a - b);
            break;
        case MUL:
            b = pop(vm); a = pop(vm);
            push(vm, a * b);
            break;
        case DIV:
            b = pop(vm); a = pop(vm);
            if (b == 0) { fprintf(stderr, "除零\n"); return 1; }
            push(vm, a / b);
            break;
        case MOD:
            b = pop(vm); a = pop(vm);
            if (b == 0) { fprintf(stderr, "除零\n"); return 1; }
            push(vm, a % b);
            break;

        case LOAD: {
            uint8_t idx = read_u8(vm->code, &vm->pc);
            if (idx >= vm->var_count) { fprintf(stderr, "越界变量: %d\n", idx); return 1; }
            push(vm, vm->vars[idx]);
            break;
        }
        case STORE: {
            uint8_t idx = read_u8(vm->code, &vm->pc);
            if (idx >= vm->var_count) { fprintf(stderr, "越界变量: %d\n", idx); return 1; }
            vm->vars[idx] = pop(vm);
            break;
        }

        case JMP: {
            int16_t off = read_i16(vm->code, &vm->pc);
            vm->pc += off;
            break;
        }
        case JZ: {
            int16_t off = read_i16(vm->code, &vm->pc);
            if (pop(vm) == 0) vm->pc += off;
            break;
        }
        case JNZ: {
            int16_t off = read_i16(vm->code, &vm->pc);
            if (pop(vm) != 0) vm->pc += off;
            break;
        }

        case CALL: {
            int16_t addr = read_i16(vm->code, &vm->pc);
            if (vm->call_depth >= 32) { fprintf(stderr, "调用栈溢出\n"); return 1; }
            vm->call_stack[vm->call_depth++] = vm->pc;
            vm->pc = addr;
            break;
        }
        case RET:
            if (vm->call_depth == 0) return 0;
            vm->pc = vm->call_stack[--vm->call_depth];
            break;

        case PRINT:
            a = pop(vm);
            printf("%d\n", (int)a);
            break;

        case IO_READ: {
            uint8_t id = (uint8_t)pop(vm);
            if (id < _dev_count && _devices[id].read)
                push(vm, _devices[id].read(id));
            else
                push(vm, 0);
            break;
        }
        case IO_WRITE: {
            a = pop(vm);
            uint8_t id = (uint8_t)pop(vm);
            if (id < _dev_count && _devices[id].write)
                _devices[id].write(id, a);
            break;
        }
        case WAIT: {
            int32_t ms = pop(vm);
#ifdef _WIN32
            Sleep(ms);
#else
            struct timespec ts = {ms / 1000, (ms % 1000) * 1000000L};
            nanosleep(&ts, NULL);
#endif
            break;
        }

        case EQ:  b = pop(vm); a = pop(vm); push(vm, a == b ? 1 : 0); break;
        case NE:  b = pop(vm); a = pop(vm); push(vm, a != b ? 1 : 0); break;
        case GT:  b = pop(vm); a = pop(vm); push(vm, a > b  ? 1 : 0); break;
        case LT:  b = pop(vm); a = pop(vm); push(vm, a < b  ? 1 : 0); break;
        case GTE: b = pop(vm); a = pop(vm); push(vm, a >= b ? 1 : 0); break;
        case LTE: b = pop(vm); a = pop(vm); push(vm, a <= b ? 1 : 0); break;
        case NOT: a = pop(vm); push(vm, a == 0 ? 1 : 0); break;

        case HALT:
            return 0;
        default:
            fprintf(stderr, "未知指令: 0x%02X @ 0x%04x\n", op, vm->pc - 1);
            return 1;
        }
    }
}

/* ── 加载固件 ────────────────────────────────────── */
int vm_load(VM *vm, const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) { perror(path); return 1; }

    uint8_t hdr[8];
    if (fread(hdr, 1, 8, fp) != 8) { fprintf(stderr, "头部读取失败\n"); fclose(fp); return 1; }
    if (memcmp(hdr, "SAN0", 4) != 0) { fprintf(stderr, "非法固件格式\n"); fclose(fp); return 1; }

    vm->var_count = hdr[5];
    uint32_t code_size;
    memcpy(&code_size, hdr + 6, 2);

    uint8_t *code = (uint8_t*)malloc(code_size);
    if (!code) { fprintf(stderr, "内存不足\n"); fclose(fp); return 1; }
    if (fread(code, 1, code_size, fp) != code_size) {
        fprintf(stderr, "代码读取失败\n"); free(code); fclose(fp); return 1;
    }
    fclose(fp);

    memset(vm, 0, sizeof(*vm));
    vm->code = code;
    vm->var_count = vm->var_count > VAR_MAX ? VAR_MAX : vm->var_count;
    return 0;
}

/* ── 原生设备示例 ──────────────────────────────── */
static int32_t mock_sensor_read(uint8_t id) {
    static int val = 0;
    val = (val + 1) % 100;
    return val;
}
static void mock_actuator_write(uint8_t id, int32_t val) {
    printf("  [执行器 %d] = %d\n", id, (int)val);
}

/* ── 主入口 ──────────────────────────────────────── */
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "用法: %s firmware.bin\n", argv[0]);
        return 1;
    }

    vm_register_device(0, mock_sensor_read, NULL);
    vm_register_device(1, NULL, mock_actuator_write);

    VM vm;
    if (vm_load(&vm, argv[1])) return 1;

    int ret = vm_run(&vm);
    free((void*)vm.code);
    return ret;
}
