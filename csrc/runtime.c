/**
 * runtime.c — 三言平坦字节码 C 解释器（52 指令完整版）
 *
 * 值系统: void* 栈值，LSB=1 为标记整数，LSB=0 为堆对象（带类型标签）。
 * 编译:   gcc -o runtime runtime.c && ./runtime firmware.bin
 * STM32:  arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os ...
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#include <unistd.h>
#endif

/* ── 配置 ── */
#ifndef VAR_MAX
#define VAR_MAX 256
#endif
#ifndef STACK_MAX
#define STACK_MAX 512
#endif
#ifndef NATIVE_DEV_MAX
#define NATIVE_DEV_MAX 16
#endif
#ifndef CALL_STACK_DEPTH
#define CALL_STACK_DEPTH 64
#endif

/* ── 堆对象类型标签 ── */
typedef enum { TYPE_STR = 0x535452, TYPE_LIST = 0x4C4953, TYPE_DICT = 0x444943 } ObjType;

#define OBJ_HDR ObjType type

/* ── 指令码 ── */
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
    CONCAT   = 0x19,
    STRLEN   = 0x1A,
    STRSUB   = 0x1B,
    STREQ    = 0x1C,
    DICT     = 0x1D,
    DICT_GET = 0x1E,
    DICT_SET = 0x1F,
    DICT_HAS = 0x20,
    IS_NUM   = 0x21,
    IS_STR   = 0x22,
    IS_LIST  = 0x23,
    SAME     = 0x24,
    GET      = 0x25,
    SET_ELEM = 0x26,
    LIST_NEW = 0x27,
    LIST_CCAT = 0x28,
    SLICE    = 0x29,
    LIST_LEN = 0x2A,
    READ_FILE = 0x2B,
    WRITE_FILE = 0x2C,
    PUSH_STR = 0x2D,
    IMPORT   = 0x2E,
    CALL_EXT = 0x2F,
    WRITE_BIN = 0x30,
    ORD      = 0x31,
    DICT_KEYS = 0x32,
    HALT     = 0xFF,
} Opcode;

/* ── 标记指针值 ───────────────────────────────── */
static inline void *tag_i(int32_t val) {
    return (void*)((intptr_t)(((int64_t)val << 1) | 1));
}
static inline int32_t untag_i(void *p) {
    return (int32_t)((intptr_t)p >> 1);
}
static inline int is_int_val(void *p) {
    return ((intptr_t)p & 1) != 0;
}
static inline int32_t to_int(void *p) {
    return is_int_val(p) ? untag_i(p) : 0;
}

/* ── 字符串 ───────────────────────────────────── */
typedef struct { OBJ_HDR; int32_t len; char data[]; } rt_str_t;

static rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t n = (int32_t)strlen(s);
    rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + n + 1);
    if (!r) return NULL;
    r->type = TYPE_STR;
    r->len = n;
    memcpy(r->data, s, n + 1);
    return r;
}

static const char *rt_str_c(void *p) {
    if (!p || is_int_val(p)) return "";
    return ((rt_str_t*)p)->data;
}

/* ── 列表 ───────────────────────────────────── */
typedef struct { OBJ_HDR; int32_t len; int32_t cap; void **items; } rt_list_t;

static rt_list_t *rt_list_new(void) {
    rt_list_t *l = (rt_list_t*)calloc(1, sizeof(rt_list_t));
    if (!l) return NULL;
    l->type = TYPE_LIST;
    l->cap = 4;
    l->items = (void**)calloc(4, sizeof(void*));
    return l;
}

static void rt_list_push(rt_list_t *l, void *v) {
    if (!l) return;
    if (l->len >= l->cap) {
        l->cap *= 2;
        l->items = (void**)realloc(l->items, (size_t)l->cap * sizeof(void*));
    }
    l->items[l->len++] = v;
}

/* ── 字典（支持 int 和 string 键，动态扩容）─────── */
#define DICT_INIT_CAP 16
typedef struct { void *k; void *v; } rt_entry_t;
typedef struct { OBJ_HDR; int32_t n; int32_t cap; rt_entry_t *entries; } rt_dict_t;

static rt_dict_t *rt_dict_new(void) {
    rt_dict_t *d = (rt_dict_t*)calloc(1, sizeof(rt_dict_t));
    if (!d) return NULL;
    d->type = TYPE_DICT;
    d->cap = DICT_INIT_CAP;
    d->entries = (rt_entry_t*)calloc(DICT_INIT_CAP, sizeof(rt_entry_t));
    if (!d->entries) { free(d); return NULL; }
    return d;
}

/* 比较两个键是否相等（处理 int 和 string）*/
static int key_eq(void *a, void *b) {
    if (is_int_val(a) && is_int_val(b)) return untag_i(a) == untag_i(b);
    if (!is_int_val(a) && !is_int_val(b) && a && b)
        return strcmp(((rt_str_t*)a)->data, ((rt_str_t*)b)->data) == 0;
    return a == b;
}

static int rt_dict_find(rt_dict_t *d, void *k) {
    if (!d) return -1;
    for (int32_t i = 0; i < d->n; i++)
        if (key_eq(d->entries[i].k, k)) return i;
    return -1;
}

static void rt_dict_set(rt_dict_t *d, void *k, void *v) {
    if (!d) return;
    int i = rt_dict_find(d, k);
    if (i >= 0) { d->entries[i].v = v; return; }
    if (d->n >= d->cap) {
        d->cap *= 2;
        d->entries = (rt_entry_t*)realloc(d->entries, (size_t)d->cap * sizeof(rt_entry_t));
    }
    d->entries[d->n].k = is_int_val(k) ? k : (void*)rt_str_new(rt_str_c(k));
    d->entries[d->n].v = v;
    d->n++;
}

static void *rt_dict_get(rt_dict_t *d, void *k) {
    int i = rt_dict_find(d, k);
    return i >= 0 ? d->entries[i].v : tag_i(0);
}

static int rt_dict_has(rt_dict_t *d, void *k) {
    return rt_dict_find(d, k) >= 0 ? 1 : 0;
}

/* ── 递归值打印 ──────────────────────────────── */
static void print_value(void *v) {
    if (!v) { printf("0"); return; }
    if (is_int_val(v)) { printf("%d", untag_i(v)); return; }
    switch (*(ObjType*)v) {
    case TYPE_STR: printf("%s", rt_str_c(v)); break;
    case TYPE_LIST: {
        rt_list_t *l = (rt_list_t*)v;
        printf("[");
        for (int32_t i = 0; i < l->len; i++) {
            if (i > 0) printf(", ");
            print_value(l->items[i]);
        }
        printf("]");
        break;
    }
    case TYPE_DICT: {
        rt_dict_t *d = (rt_dict_t*)v;
        printf("{");
        for (int32_t i = 0; i < d->n; i++) {
            if (i > 0) printf(", ");
            print_value(d->entries[i].k);
            printf(": ");
            print_value(d->entries[i].v);
        }
        printf("}");
        break;
    }
    default: printf("0"); break;
    }
}

/* ── 类型检查 ── */
static int is_obj_type(void *p, ObjType t) {
    return p && !is_int_val(p) && ((rt_str_t*)p)->type == t;
}
static int is_str(void *p)  { return is_obj_type(p, TYPE_STR); }
static int is_list(void *p) { return is_obj_type(p, TYPE_LIST); }
static int is_dict(void *p) { return is_obj_type(p, TYPE_DICT); }

/* ── UTF-16LE → UTF-8 ── */
static char *utf16le_to_utf8(const uint8_t *src, int codepoints) {
    char *out = (char*)malloc((size_t)codepoints * 4 + 1);
    if (!out) return NULL;
    int pos = 0;
    for (int i = 0; i < codepoints; i++) {
        uint32_t cp = src[0] | ((uint32_t)src[1] << 8);
        src += 2;
        if (cp < 0x80) {
            out[pos++] = (char)cp;
        } else if (cp < 0x800) {
            out[pos++] = (char)(0xC0 | (cp >> 6));
            out[pos++] = (char)(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out[pos++] = (char)(0xE0 | (cp >> 12));
            out[pos++] = (char)(0x80 | ((cp >> 6) & 0x3F));
            out[pos++] = (char)(0x80 | (cp & 0x3F));
        } else {
            out[pos++] = (char)(0xF0 | (cp >> 18));
            out[pos++] = (char)(0x80 | ((cp >> 12) & 0x3F));
            out[pos++] = (char)(0x80 | ((cp >> 6) & 0x3F));
            out[pos++] = (char)(0x80 | (cp & 0x3F));
        }
    }
    out[pos] = '\0';
    return out;
}

/* ── 原生设备 ── */
typedef int32_t (*native_read_fn)(uint8_t dev_id);
typedef void    (*native_write_fn)(uint8_t dev_id, int32_t val);
typedef struct { native_read_fn read; native_write_fn write; } NativeDevice;
static NativeDevice _devs[NATIVE_DEV_MAX];
static uint8_t _dev_cnt;

void vm_register_device(uint8_t id, native_read_fn r, native_write_fn w) {
    if (id < NATIVE_DEV_MAX) { _devs[id] = (NativeDevice){r, w}; _dev_cnt++; }
}

/* ── 调用栈帧 ── */
typedef struct {
    uint32_t ret_pc;
    int16_t stack_base;
    void *saved_vars[VAR_MAX];
    uint8_t saved_var_cnt;
} CallFrame;

/* ── VM ── */
typedef struct {
    void *stack[STACK_MAX];
    int16_t sp;
    void *vars[VAR_MAX];
    uint8_t var_count;
    const uint8_t *code;
    uint32_t code_len;
    uint32_t pc;
    CallFrame call_stack[CALL_STACK_DEPTH];
    uint8_t call_depth;
    int halted;
} VM;

/* ── 栈操作 ── */
static void push(VM *vm, void *v) {
    if (vm->sp >= STACK_MAX) { fprintf(stderr, "栈溢出\n"); exit(1); }
    vm->stack[vm->sp++] = v;
}
static void *pop(VM *vm) {
    if (vm->sp <= 0) { fprintf(stderr, "栈下溢\n"); exit(1); }
    return vm->stack[--vm->sp];
}

/* ── 读取操作数 ── */
static uint8_t rd_u8(const uint8_t *c, uint32_t *pc) { return c[(*pc)++]; }
static int32_t rd_i32(const uint8_t *c, uint32_t *pc) {
    int32_t v; memcpy(&v, c + *pc, 4); *pc += 4; return v;
}
static int16_t rd_i16(const uint8_t *c, uint32_t *pc) {
    int16_t v; memcpy(&v, c + *pc, 2); *pc += 2; return v;
}

/* ── 条件跳转用 ── */
static int val_true(void *v) {
    if (is_int_val(v)) return untag_i(v) != 0;
    return v != NULL;
}

/* ── 内置模块管理 ── */
#define MOD_MAX 16
static struct { void *code; uint32_t size; uint8_t var_cnt; void *vars[VAR_MAX]; } _mods[MOD_MAX];
static int _mod_cnt;

/* ═══════════════════════════════════════════════════
 * 主解释循环
 * ═══════════════════════════════════════════════════ */
int vm_run(VM *vm) {
    while (!vm->halted) {
        if (vm->pc >= vm->code_len) { vm->halted = 1; break; }
        uint8_t op = rd_u8(vm->code, &vm->pc);
        void *a, *b;
        int32_t ia, ib;

        switch (op) {

        case NOP: break;

        /* ── 栈操作 ── */
        case PUSH_I:
            push(vm, tag_i(rd_i32(vm->code, &vm->pc)));
            break;

        case PUSH_STR: {
            int len = rd_u8(vm->code, &vm->pc);
            char *utf8 = utf16le_to_utf8(vm->code + vm->pc, len);
            vm->pc += len * 2;
            push(vm, rt_str_new(utf8));
            free(utf8);
            break;
        }

        /* ── 算术 ── */
        case ADD: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) + to_int(b))); break;
        case SUB: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) - to_int(b))); break;
        case MUL: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) * to_int(b))); break;
        case DIV: b = pop(vm); a = pop(vm);
            ib = to_int(b); push(vm, ib ? tag_i(to_int(a) / ib) : tag_i(0)); break;
        case MOD: b = pop(vm); a = pop(vm);
            ib = to_int(b); push(vm, ib ? tag_i(to_int(a) % ib) : tag_i(0)); break;

        /* ── 比较 ── */
        case EQ:  b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) == to_int(b) ? 1 : 0)); break;
        case NE:  b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) != to_int(b) ? 1 : 0)); break;
        case GT:  b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) > to_int(b) ? 1 : 0)); break;
        case LT:  b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) < to_int(b) ? 1 : 0)); break;
        case GTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) >= to_int(b) ? 1 : 0)); break;
        case LTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) <= to_int(b) ? 1 : 0)); break;
        case NOT: a = pop(vm);
            push(vm, tag_i(!to_int(a))); break;

        case LOAD: {
            uint8_t idx = rd_u8(vm->code, &vm->pc);
            push(vm, vm->vars[idx]);
            break;
        }
        case STORE: {
            uint8_t idx = rd_u8(vm->code, &vm->pc);
            vm->vars[idx] = pop(vm);
            break;
        }

        /* ── 控制流 ── */
        case JMP: {
            int16_t off = rd_i16(vm->code, &vm->pc);
            vm->pc += off;
            break;
        }
        case JZ: {
            int16_t off = rd_i16(vm->code, &vm->pc);
            if (!val_true(pop(vm))) vm->pc += off;
            break;
        }
        case JNZ: {
            int16_t off = rd_i16(vm->code, &vm->pc);
            if (val_true(pop(vm))) vm->pc += off;
            break;
        }
        case CALL: {
            int16_t addr = rd_i16(vm->code, &vm->pc);
            if (addr == 0) break;
            if (vm->call_depth >= CALL_STACK_DEPTH) { fprintf(stderr, "调用栈溢出\n"); return 1; }
            // 扫描目标地址连续 STORE 指令个数 = 参数数量（与 Python VM 一致）
            int32_t arg_count = 0;
            uint32_t p = (uint32_t)addr;
            while (p + 1 < vm->code_len && vm->code[p] == STORE) {
                arg_count++;
                p += 2;
            }
            CallFrame *fr = &vm->call_stack[vm->call_depth++];
            fr->ret_pc = vm->pc;
            fr->stack_base = vm->sp - arg_count;
            fr->saved_var_cnt = vm->var_count;
            memcpy(fr->saved_vars, vm->vars, sizeof(void*) * vm->var_count);
            vm->pc = (uint32_t)addr;
            break;
        }
        case RET: {
            if (vm->call_depth == 0) { vm->halted = 1; break; }
            CallFrame *fr = &vm->call_stack[--vm->call_depth];
            void *ret_val = vm->sp > fr->stack_base ? vm->stack[--vm->sp] : tag_i(0);
            vm->sp = fr->stack_base;
            memcpy(vm->vars, fr->saved_vars, sizeof(void*) * fr->saved_var_cnt);
            vm->var_count = fr->saved_var_cnt;
            push(vm, ret_val);
            vm->pc = fr->ret_pc;
            break;
        }

        /* ── 输出 ── */
        case PRINT: {
            print_value(pop(vm));
            printf("\n");
            break;
        }

        /* ── I/O ── */
        case IO_READ: {
            uint8_t id = (uint8_t)to_int(pop(vm));
            if (id < _dev_cnt && _devs[id].read) push(vm, tag_i(_devs[id].read(id)));
            else push(vm, tag_i(0));
            break;
        }
        case IO_WRITE: {
            a = pop(vm);
            uint8_t id = (uint8_t)to_int(pop(vm));
            if (id < _dev_cnt && _devs[id].write) _devs[id].write(id, to_int(a));
            break;
        }

        /* ── 等待 ── */
        case WAIT: {
            int32_t ms = to_int(pop(vm));
#ifdef _WIN32
            Sleep(ms);
#else
            struct timespec ts = {ms / 1000, (ms % 1000) * 1000000L};
            nanosleep(&ts, NULL);
#endif
            break;
        }

        /* ── 字符串操作 ── */
        case CONCAT: {
            int32_t n = to_int(pop(vm));
            if (n <= 0) { push(vm, rt_str_new("")); break; }
            // 收集所有字符串并计算总长度
            int32_t total = 0;
            int32_t *lens = (int32_t*)malloc((size_t)n * sizeof(int32_t));
            const char **strs = (const char**)malloc((size_t)n * sizeof(char*));
            if (!lens || !strs) { free(lens); free(strs); push(vm, rt_str_new("")); break; }
            for (int32_t i = n - 1; i >= 0; i--) {
                void *item = pop(vm);
                strs[i] = rt_str_c(item);
                lens[i] = (int32_t)strlen(strs[i]);
                total += lens[i];
            }
            rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + total + 1);
            if (!r) { free(lens); free(strs); push(vm, rt_str_new("")); break; }
            r->type = TYPE_STR;
            r->len = total;
            char *dst = r->data;
            for (int32_t i = 0; i < n; i++) {
                memcpy(dst, strs[i], lens[i]);
                dst += lens[i];
            }
            *dst = '\0';
            free(lens); free(strs);
            push(vm, r);
            break;
        }
        case STRLEN: {
            a = pop(vm);
            if (is_int_val(a)) {
                char buf[16];
                snprintf(buf, sizeof(buf), "%d", untag_i(a));
                push(vm, tag_i((int32_t)strlen(buf)));
            } else push(vm, tag_i((int32_t)strlen(rt_str_c(a))));
            break;
        }
        case STRSUB: {
            int32_t n = to_int(pop(vm));
            int32_t st = to_int(pop(vm));
            const char *s = rt_str_c(pop(vm));
            int32_t sl = (int32_t)strlen(s);
            if (st < 0) st = 0;
            if (st > sl) st = sl;
            if (n < 0) n = 0;
            if (st + n > sl) n = sl - st;
            char *buf = (char*)malloc((size_t)n + 1);
            if (buf) { memcpy(buf, s + st, (size_t)n); buf[n] = '\0'; }
            push(vm, rt_str_new(buf ? buf : ""));
            free(buf);
            break;
        }
        case STREQ: {
            b = pop(vm); a = pop(vm);
            push(vm, tag_i(strcmp(rt_str_c(a), rt_str_c(b)) == 0 ? 1 : 0));
            break;
        }
        case ORD: {
            const char *s = rt_str_c(pop(vm));
            push(vm, tag_i(s[0] ? (unsigned char)s[0] : 0));
            break;
        }

        /* ── 类型检查 ── */
        case IS_NUM: push(vm, tag_i(is_int_val(pop(vm)) ? 1 : 0)); break;
        case IS_STR: push(vm, tag_i(is_str(pop(vm)) ? 1 : 0)); break;
        case IS_LIST: push(vm, tag_i(is_list(pop(vm)) ? 1 : 0)); break;
        case SAME: b = pop(vm); a = pop(vm); push(vm, tag_i(a == b ? 1 : 0)); break;

        /* ── 容器操作 ── */
        case GET: {
            ib = to_int(pop(vm));
            a = pop(vm);
            if (is_int_val(a)) { push(vm, tag_i(0)); break; }
            if (is_str(a)) {
                const char *s = rt_str_c(a);
                int32_t sl = (int32_t)strlen(s);
                if (ib >= 0 && ib < sl) { char buf[2] = {s[ib], 0}; push(vm, rt_str_new(buf)); }
                else push(vm, tag_i(0));
            } else if (is_list(a)) {
                rt_list_t *l = (rt_list_t*)a;
                push(vm, (ib >= 0 && ib < l->len) ? l->items[ib] : tag_i(0));
            } else push(vm, tag_i(0));
            break;
        }
        case SET_ELEM: {
            void *val = pop(vm);
            ib = to_int(pop(vm));
            a = pop(vm);
            if (is_list(a) && ib >= 0 && ib < ((rt_list_t*)a)->len)
                ((rt_list_t*)a)->items[ib] = val;
            push(vm, a);
            break;
        }
        case LIST_NEW: {
            int32_t n = to_int(pop(vm));
            rt_list_t *l = rt_list_new();
            int16_t base = vm->sp - n;
            for (int32_t i = 0; i < n; i++)
                rt_list_push(l, vm->stack[base + i]);
            vm->sp -= n;
            push(vm, l);
            break;
        }
        case LIST_CCAT: {
            b = pop(vm); a = pop(vm);
            rt_list_t *r = rt_list_new();
            rt_list_t *la = is_list(a) ? (rt_list_t*)a : NULL;
            rt_list_t *lb = is_list(b) ? (rt_list_t*)b : NULL;
            if (la) for (int32_t i = 0; i < la->len; i++) rt_list_push(r, la->items[i]);
            if (lb) for (int32_t i = 0; i < lb->len; i++) rt_list_push(r, lb->items[i]);
            push(vm, r);
            break;
        }
        case SLICE: {
            int32_t end = to_int(pop(vm));
            int32_t start = to_int(pop(vm));
            a = pop(vm);
            if (is_int_val(a)) { push(vm, rt_list_new()); break; }
            if (is_str(a)) {
                const char *s = rt_str_c(a);
                int32_t sl = (int32_t)strlen(s);
                if (start < 0) start = 0;
                if (end > sl) end = sl;
                if (start > end) start = end;
                char *buf = (char*)malloc((size_t)(end - start) + 1);
                if (buf) { memcpy(buf, s + start, (size_t)(end - start)); buf[end - start] = '\0'; }
                push(vm, rt_str_new(buf ? buf : ""));
                free(buf);
            } else if (is_list(a)) {
                rt_list_t *l = (rt_list_t*)a;
                if (start < 0) start = 0;
                if (end > l->len) end = l->len;
                if (start > end) start = end;
                rt_list_t *r = rt_list_new();
                for (int32_t i = start; i < end; i++) rt_list_push(r, l->items[i]);
                push(vm, r);
            } else push(vm, rt_list_new());
            break;
        }
        case LIST_LEN: {
            a = pop(vm);
            if (is_int_val(a)) push(vm, tag_i(0));
            else if (is_str(a)) push(vm, tag_i((int32_t)strlen(rt_str_c(a))));
            else if (is_list(a)) push(vm, tag_i(((rt_list_t*)a)->len));
            else push(vm, tag_i(0));
            break;
        }

        /* ── 字典操作 ── */
        case DICT: {
            int32_t n = to_int(pop(vm));
            rt_dict_t *d = rt_dict_new();
            for (int32_t i = 0; i < n; i++) {
                void *val = pop(vm);
                void *key = pop(vm);
                rt_dict_set(d, key, val);
            }
            push(vm, d);
            break;
        }
        case DICT_GET: {
            void *k = pop(vm);
            a = pop(vm);
            push(vm, is_dict(a) ? rt_dict_get((rt_dict_t*)a, k) : tag_i(0));
            break;
        }
        case DICT_SET: {
            void *val = pop(vm);
            void *k = pop(vm);
            a = pop(vm);
            if (is_dict(a)) rt_dict_set((rt_dict_t*)a, k, val);
            break;
        }
        case DICT_HAS: {
            void *k = pop(vm);
            a = pop(vm);
            push(vm, is_dict(a) ? tag_i(rt_dict_has((rt_dict_t*)a, k)) : tag_i(0));
            break;
        }
        case DICT_KEYS: {
            a = pop(vm);
            if (is_dict(a)) {
                rt_dict_t *d = (rt_dict_t*)a;
                rt_list_t *l = rt_list_new();
                for (int32_t i = 0; i < d->n; i++) {
                    void *k = d->entries[i].k;
                    if (is_int_val(k)) rt_list_push(l, k);
                    else rt_list_push(l, rt_str_new(rt_str_c(k)));
                }
                push(vm, l);
            } else push(vm, rt_list_new());
            break;
        }

        /* ── 文件操作 ── */
        case READ_FILE: {
            const char *path = rt_str_c(pop(vm));
            FILE *f = fopen(path, "rb");
            if (!f) { push(vm, rt_str_new("")); break; }
            fseek(f, 0, SEEK_END);
            long sz = ftell(f);
            fseek(f, 0, SEEK_SET);
            char *buf = (char*)malloc((size_t)sz + 1);
            if (buf) {
                size_t n = fread(buf, 1, (size_t)sz, f);
                buf[n] = '\0';
            }
            fclose(f);
            push(vm, rt_str_new(buf ? buf : ""));
            free(buf);
            break;
        }
        case WRITE_FILE: {
            const char *data = rt_str_c(pop(vm));
            const char *path = rt_str_c(pop(vm));
            FILE *f = fopen(path, "w");
            if (!f) { push(vm, tag_i(0)); break; }
            fwrite(data, 1, strlen(data), f);
            fclose(f);
            push(vm, tag_i(1));
            break;
        }
        case WRITE_BIN: {
            a = pop(vm);
            const char *path = rt_str_c(pop(vm));
            if (!is_list(a)) { push(vm, tag_i(0)); break; }
            rt_list_t *l = (rt_list_t*)a;
            FILE *f = fopen(path, "wb");
            if (!f) { push(vm, tag_i(0)); break; }
            for (int32_t i = 0; i < l->len; i++)
                putc((unsigned char)to_int(l->items[i]), f);
            fclose(f);
            push(vm, tag_i(1));
            break;
        }

        /* ── 模块操作 ── */
        case IMPORT: {
            const char *path = rt_str_c(pop(vm));
            if (_mod_cnt >= MOD_MAX) { push(vm, tag_i(0)); break; }
            FILE *f = fopen(path, "rb");
            if (!f) { push(vm, tag_i(0)); break; }
            uint8_t hdr[8];
            if (fread(hdr, 1, 8, f) != 8 || memcmp(hdr, "SAN0", 4) != 0) {
                fclose(f); push(vm, tag_i(0)); break;
            }
            uint32_t sz;
            memcpy(&sz, hdr + 6, 2);
            uint8_t *code = (uint8_t*)malloc(sz);
            if (!code) { fclose(f); push(vm, tag_i(0)); break; }
            if (fread(code, 1, sz, f) != sz) {
                free(code); fclose(f); push(vm, tag_i(0)); break;
            }
            fclose(f);
            int mid = _mod_cnt;
            _mods[mid].code = code;
            _mods[mid].size = sz;
            _mods[mid].var_cnt = hdr[5];
            memset(_mods[mid].vars, 0, sizeof(void*) * VAR_MAX);
            push(vm, tag_i(mid + 1));
            _mod_cnt++;
            break;
        }
        case CALL_EXT: {
            int32_t mod_id = to_int(pop(vm));
            pop(vm); /* func_name */
            int32_t arg_cnt = to_int(pop(vm));
            for (int32_t i = 0; i < arg_cnt; i++) pop(vm);
            if (mod_id < 1 || mod_id > _mod_cnt) {
                push(vm, tag_i(0));
                break;
            }
            int mid = mod_id - 1;
            VM *caller = vm;
            VM mod_vm;
            memset(&mod_vm, 0, sizeof(mod_vm));
            mod_vm.code = _mods[mid].code;
            mod_vm.code_len = _mods[mid].size;
            mod_vm.var_count = _mods[mid].var_cnt;
            vm_run(&mod_vm);
            void *result = mod_vm.sp > 0 ? mod_vm.stack[mod_vm.sp - 1] : tag_i(0);
            memcpy(_mods[mid].vars, mod_vm.vars, sizeof(void*) * VAR_MAX);
            push(caller, result);
            break;
        }

        case HALT:
            vm->halted = 1;
            break;

        default:
            fprintf(stderr, "未知指令: 0x%02X @ 0x%04x\n", op, vm->pc - 1);
            return 1;
        }
    }
    return 0;
}

/* ── 加载固件 ── */
int vm_load(VM *vm, const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) { perror(path); return 1; }

    uint8_t hdr[8];
    if (fread(hdr, 1, 8, fp) != 8) { fprintf(stderr, "头部读取失败\n"); fclose(fp); return 1; }
    if (memcmp(hdr, "SAN0", 4) != 0) { fprintf(stderr, "非法固件格式\n"); fclose(fp); return 1; }

    uint8_t vc = hdr[5];
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
    vm->code_len = code_size;
    vm->var_count = vc;
    return 0;
}

/* ── 原生设备示例 ── */
static int32_t mock_sensor_read(uint8_t id) {
    static int val = 0;
    (void)id;
    val = (val + 1) % 100;
    return val;
}
static void mock_actuator_write(uint8_t id, int32_t val) {
    printf("  [执行器 %d] = %d\n", id, (int)val);
}

/* ── 主入口 ── */
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
