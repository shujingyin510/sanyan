/**
 * runtime.c — 三言字节码 C 解释器（52 指令完整版）
 *
 * 值系统: void* 栈值，LSB=1 为标记整数，LSB=0 为堆对象（带类型标签）。
 * 编译:   gcc -o runtime runtime.c && ./runtime firmware.bin
 * STM32:  arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os ...
 *
 * ⚠ 已知限制:
 *   - 无堆对象释放 (no free): 字符串/列表/字典分配后不回收。
 *     批处理场景可接受 (程序退出时OS回收)，嵌入式长期运行需改进。
 *   - snprintf 固定 1024 字节缓冲区: 超长路径/字符串可能截断。
 *     改进方向: 使用 snprintf(NULL, 0, ...) 动态计算长度。
 *   - CALL opcode: 参数计数依赖扫描函数入口连续 STORE 指令。
 *     非标准函数格式（STORE 中间插入其他指令）会误计算。
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define mkdir(p, m) _mkdir(p)
#else
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>
#endif

#include "runtime_common.h"

/* ── 配置 ── */
#ifndef VAR_MAX
#define VAR_MAX 256
#endif
#ifndef STACK_MAX
#define STACK_MAX 8192
#endif
#ifndef CALL_STACK_DEPTH
#define CALL_STACK_DEPTH 255
#endif
#ifndef NATIVE_DEV_MAX
#define NATIVE_DEV_MAX 16
#endif

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
    JMP32    = 0x33,
    OR       = 0x34,
    AND      = 0x35,
    STR_FIND = 0x36,
    STR_TO_LIST = 0x37,
    STR_STARTSWITH = 0x38,
    STR_CONTAINS = 0x39,
    DICT_LEN = 0x3A,
    /* 位运算与字节操作 */
    BIT_AND = 0x3B,
    BIT_OR  = 0x3C,
    BIT_XOR = 0x3D,
    BIT_NOT = 0x3E,
    SHIFT_L = 0x3F,
    SHIFT_R = 0x40,
    BIT_SET = 0x41,
    BIT_CLR = 0x42,
    BIT_TGL = 0x43,
    BIT_TST = 0x44,
    LO_BYTE = 0x45,
    HI_BYTE = 0x46,
    MRG_BYT = 0x47,
    PUSH_FLOAT = 0x48,  /* IEEE 754 double (8 bytes) */
    /* 终止 */
    HALT     = 0xFF,
} Opcode;


/* ── UTF-8 字符操作 ──────────────────────────── */
/* UTF-8 编码：1 字节(0xxxxxxx), 2 字节(110xxxxx 10xxxxxx),
   3 字节(1110xxxx 10xxxxxx 10xxxxxx), 4 字节(11110xxx ...)
   后续字节以 10 开头（0xC0 掩码 = 0x80）。 */
static size_t utf8_char_len(const char *s) {
    size_t count = 0;
    while (*s) {
        if ((*s & 0xC0) != 0x80) count++;  /* 跳过后续字节 */
        s++;
    }
    return count;
}

/* 找到 UTF-8 字符串中第 idx 个字符的字节偏移量 */
static int32_t utf8_byte_offset(const char *s, int32_t idx) {
    int32_t count = 0;
    const char *p = s;
    while (*p && count < idx) {
        if ((*p & 0xC0) != 0x80) count++;
        p++;
    }
    return (int32_t)(p - s);
}

/* 从字节偏移量开始复制 n 个 UTF-8 字符 */
static char *utf8_substr(const char *s, int32_t start_char, int32_t n_char) {
    int32_t byte_st = utf8_byte_offset(s, start_char);
    int32_t byte_end = utf8_byte_offset(s + byte_st, n_char) + byte_st;
    size_t len = (size_t)(byte_end - byte_st);
    char *buf = (char*)malloc(len + 1);
    if (buf) { memcpy(buf, s + byte_st, len); buf[len] = '\0'; }
    return buf;
}

/* ── 字符串操作 ───────────────────────────────── */
static rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t n = (int32_t)strlen(s);
    rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + n + 1);
    if (!r) return NULL;
    r->h_type = OBJ_STRING;
    r->len = n;
    memcpy(r->data, s, n + 1);
    return r;
}

/* ── 列表操作 ───────────────────────────────── */
static rt_list_t *rt_list_new(void) {
    rt_list_t *l = (rt_list_t*)calloc(1, sizeof(rt_list_t));
    if (!l) return NULL;
    l->h_type = OBJ_LIST;
    l->cap = 4;
    l->items = (void**)calloc(4, sizeof(void*));
    return l;
}

static void rt_list_push(rt_list_t *l, void *v) {
    if (!l) return;
    if (l->len >= l->cap) {
        int32_t new_cap = l->cap * 2;
        void **new_items = (void**)realloc(l->items, (size_t)new_cap * sizeof(void*));
        if (!new_items) return;  /* realloc 失败：保留旧 items，不泄漏 */
        l->items = new_items;
        l->cap = new_cap;
    }
    l->items[l->len++] = v;
}

/* ── 字典类型（csrc 专用：void* 键，开放寻址）── */
typedef struct { void *k; void *v; } rt_entry_t;
typedef struct { OBJ_HDR; int32_t n; int32_t cap; rt_entry_t *entries; } rt_dict_t;

/* ── 字典操作 ───────────────────────────────── */

/* 键哈希函数：整数用 FNV-1a 混合，字符串用 djb2 */
static uint32_t hash_key(void *k) {
    if (is_int_val(k)) {
        uint32_t h = (uint32_t)(uintptr_t)untag_i(k);
        h = ((h >> 16) ^ h) * 0x45d9f3b;
        h = ((h >> 16) ^ h) * 0x45d9f3b;
        return (h >> 16) ^ h;
    }
    /* float: 按双精度位模式哈希 */
    if (obj_type(k) == OBJ_FLOAT) {
        union { double d; uint64_t u; } fu;
        fu.d = ((rt_float_t*)k)->value;
        uint32_t lo = (uint32_t)(fu.u & 0xFFFFFFFF);
        uint32_t hi = (uint32_t)(fu.u >> 32);
        return lo ^ hi;
    }
    const char *s = rt_str_c(k);
    uint32_t h = 5381;
    while (*s) h = ((h << 5) + h) + (unsigned char)*s++;
    return h;
}

/* 比较两个键是否相等（支持 int/float/string）*/
static int key_eq(void *a, void *b) {
    if (is_int_val(a) && is_int_val(b)) return untag_i(a) == untag_i(b);
    /* float: 按位比较（含 NaN ≠ NaN，符合 IEEE 语义）*/
    if (obj_type(a) == OBJ_FLOAT && obj_type(b) == OBJ_FLOAT)
        return ((rt_float_t*)a)->value == ((rt_float_t*)b)->value;
    if (!is_int_val(a) && !is_int_val(b) && a && b
        && obj_type(a) != OBJ_FLOAT && obj_type(b) != OBJ_FLOAT)
        return strcmp(((rt_str_t*)a)->data, ((rt_str_t*)b)->data) == 0;
    return a == b;
}

/* 哈希表扩容：重新哈希所有条目到 2 倍容量（不超过 RT_DICT_MAX_CAP） */
static void rt_dict_rehash(rt_dict_t *d) {
    int32_t old_cap = d->cap;
    int32_t new_cap = old_cap * 2;
    if (new_cap > RT_DICT_MAX_CAP) {
        if (old_cap >= RT_DICT_MAX_CAP) return;  /* 已达上限，不扩容 */
        new_cap = RT_DICT_MAX_CAP;
    }
    rt_entry_t *old = d->entries;
    rt_entry_t *new_entries = (rt_entry_t*)calloc((size_t)new_cap, sizeof(rt_entry_t));
    if (!new_entries) return;  /* 分配失败：保留旧表，不泄漏 */
    d->cap = new_cap;
    d->entries = new_entries;
    for (int32_t i = 0; i < old_cap; i++) {
        if (old[i].k != NULL) {
            uint32_t h = hash_key(old[i].k);
            uint32_t idx = h & ((uint32_t)d->cap - 1);
            while (d->entries[idx].k != NULL)
                idx = (idx + 1) & ((uint32_t)d->cap - 1);
            d->entries[idx] = old[i];
        }
    }
    free(old);
}

static rt_dict_t *rt_dict_new(void) {
    rt_dict_t *d = (rt_dict_t*)calloc(1, sizeof(rt_dict_t));
    if (!d) return NULL;
    d->h_type = OBJ_DICT;
    d->cap = RT_DICT_INIT_CAP;
    d->entries = (rt_entry_t*)calloc(RT_DICT_INIT_CAP, sizeof(rt_entry_t));
    if (!d->entries) { free(d); return NULL; }
    return d;
}

/* 哈希查找：线性探测，返回槽位索引或 -1 */
static int rt_dict_find(rt_dict_t *d, void *k) {
    if (!d || d->cap == 0) return -1;
    uint32_t h = hash_key(k);
    uint32_t cap = (uint32_t)d->cap;
    uint32_t idx = h & (cap - 1);
    for (uint32_t i = 0; i < cap; i++) {
        uint32_t pos = (idx + i) & (cap - 1);
        if (d->entries[pos].k == NULL) return -1;
        if (key_eq(d->entries[pos].k, k)) return (int)pos;
    }
    return -1;
}

static void rt_dict_set(rt_dict_t *d, void *k, void *v) {
    if (!d) return;
    if (d->n >= (d->cap * RT_DICT_LOAD_FACTOR) / 100)
        rt_dict_rehash(d);
    uint32_t h = hash_key(k);
    uint32_t idx = h & ((uint32_t)d->cap - 1);
    for (uint32_t i = 0; i < (uint32_t)d->cap; i++) {
        uint32_t pos = (idx + i) & ((uint32_t)d->cap - 1);
        if (d->entries[pos].k == NULL) {
            d->entries[pos].k = is_int_val(k) ? k : (void*)rt_str_new(rt_str_c(k));
            d->entries[pos].v = v;
            d->n++;
            return;
        }
        if (key_eq(d->entries[pos].k, k)) {
            d->entries[pos].v = v;
            return;
        }
    }
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
    if (is_int_val(v)) { printf("%lld", (long long)untag_i(v)); return; }
    switch ((san_obj_type_t)((rt_str_t*)v)->h_type) {
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
        int32_t cnt = 0;
        for (int32_t i = 0; i < d->cap; i++) {
            if (d->entries[i].k != NULL) {
                if (cnt > 0) printf(", ");
                print_value(d->entries[i].k);
                printf(": ");
                print_value(d->entries[i].v);
                cnt++;
            }
        }
        printf("}");
        break;
    }
    default: printf("0"); break;
    }
}

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

/* ── 条件跳转用（三值逻辑：>0 为真，≤0 为假）── */
static int val_true(void *v) {
    if (is_int_val(v)) return untag_i(v) > 0;
    return v != NULL;
}

/* ── 内置模块管理 ── */
#define MOD_MAX 16
#define EXPORT_MAX 64
typedef struct {
    void *code;
    uint32_t size;
    uint8_t var_cnt;
    void *vars[VAR_MAX];
    int export_count;
    char export_names[EXPORT_MAX][64];
    uint32_t export_addrs[EXPORT_MAX];
} Module;
static Module _mods[MOD_MAX];
static int _mod_cnt;

/* ── 从已打开的文件指针读取导出表（文件指针必须在代码数据之后）── */
static int read_export_table(FILE *fp, Module *mod) {
    uint8_t buf[4];
    if (fread(buf, 1, 2, fp) != 2) { mod->export_count = 0; return 0; }
    uint16_t count;
    memcpy(&count, buf, 2);
    if (count > EXPORT_MAX) count = EXPORT_MAX;
    mod->export_count = 0;
    for (uint16_t i = 0; i < count; i++) {
        if (fread(buf, 1, 2, fp) != 2) break;
        uint16_t name_len;
        memcpy(&name_len, buf, 2);
        if (name_len > 63) name_len = 63;
        uint8_t *utf16 = (uint8_t*)malloc((size_t)name_len * 2);
        if (!utf16) break;
        if (fread(utf16, 1, (size_t)name_len * 2, fp) != (size_t)name_len * 2) {
            free(utf16); break;
        }
        char *utf8 = utf16le_to_utf8(utf16, name_len);
        free(utf16);
        if (!utf8) break;
        strncpy(mod->export_names[mod->export_count], utf8, 63);
        mod->export_names[mod->export_count][63] = '\0';
        free(utf8);
        if (fread(buf, 1, 4, fp) != 4) break;
        memcpy(&mod->export_addrs[mod->export_count], buf, 4);
        mod->export_count++;
    }
    return 0;
}

/* ── 根据名称查找模块导出地址 ── */
static int find_export(Module *mod, const char *name) {
    for (int i = 0; i < mod->export_count; i++) {
        if (strcmp(mod->export_names[i], name) == 0)
            return mod->export_addrs[i];
    }
    return -1;
}

/* ── .bin 字节码版本号（与 vm.py BIN_VERSION 一致）── */
#define BIN_VERSION 1

/* ── 验证 .bin 头部（严格匹配 SAN0 + 版本号检查）── */
static int check_bin_header(const uint8_t *hdr, const char *path) {
    /* 格式：magic "SAN0"(4) + ver(1) + var_cnt(1) + code_size(4) */
    if (memcmp(hdr, "SAN0", 4) != 0) {
        if (path) fprintf(stderr, "非法模块格式: %s\n", path);
        return 1;
    }
    if (hdr[4] != BIN_VERSION) {
        if (path) fprintf(stderr, "字节码版本不兼容: %s (期望 v%d, 实际 v%d)\n",
                          path, BIN_VERSION, hdr[4]);
        return 1;
    }
    return 0;
}

/* ── 三态传播辅助：如果 a 或 b 是 OBJ_TRIT，返回传播后的信度 ×100 ── */
static int trit_propagate_conf(void *a, void *b) {
    double ca = is_int_val(a) ? 1.0 : (((rt_trit_t*)a)->h_type == OBJ_TRIT ? ((rt_trit_t*)a)->confidence / 100.0 : 1.0);
    double cb = is_int_val(b) ? 1.0 : (((rt_trit_t*)b)->h_type == OBJ_TRIT ? ((rt_trit_t*)b)->confidence / 100.0 : 1.0);
    return (int)(ca * cb * 100.0);
}
static int trit_is_trit(void *v) { return !is_int_val(v) && ((rt_str_t*)v)->h_type == OBJ_TRIT; }
/* 获取单个值的信度 ×100（用于一元运算） */
static double rt_trit_confidence(void *v) {
    return is_int_val(v) ? 1.0 : (((rt_trit_t*)v)->h_type == OBJ_TRIT ? ((rt_trit_t*)v)->confidence / 100.0 : 1.0);
}

/* ═══════════════════════════════════════════════════
 * 主解释循环
 * ═══════════════════════════════════════════════════ */
int vm_run(VM *vm) {
    uint64_t step_count = 0;
    while (!vm->halted) {
        if (vm->pc >= vm->code_len) { vm->halted = 1; break; }
        if (++step_count > 50000000000ULL) {
            fprintf(stderr, "超时：步数超过 50B，PC=0x%04x sp=%d call_depth=%d\n", vm->pc, vm->sp, vm->call_depth);
            return 1;
        }
        uint8_t op = rd_u8(vm->code, &vm->pc);
        void *a, *b;
        intptr_t ib;

        switch (op) {

        case NOP: break;

        /* ── 栈操作 ── */
        case PUSH_I:
            push(vm, tag_i(rd_i32(vm->code, &vm->pc)));
            break;

        case PUSH_FLOAT: {
            /* 读取 8 字节 IEEE 754 double（little-endian）*/
            double fval;
            memcpy(&fval, vm->code + vm->pc, 8);
            vm->pc += 8;
            push(vm, rt_float_new(fval));
            break;
        }

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
            { int r = to_int(a) + to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case SUB: b = pop(vm); a = pop(vm);
            { int r = to_int(a) - to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case MUL: b = pop(vm); a = pop(vm);
            { int r = to_int(a) * to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case DIV: b = pop(vm); a = pop(vm);
            ib = to_int(b); { int r = ib ? to_int(a)/ib : 0;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case MOD: b = pop(vm); a = pop(vm);
            ib = to_int(b); { int r = ib ? to_int(a)%ib : 0;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        /* ── 位运算 ── */
        case BIT_AND: b = pop(vm); a = pop(vm);
            { int r = to_int(a) & to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case BIT_OR: b = pop(vm); a = pop(vm);
            { int r = to_int(a) | to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case BIT_XOR: b = pop(vm); a = pop(vm);
            { int r = to_int(a) ^ to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case BIT_NOT: a = pop(vm);
            { int r = ~to_int(a);
              push(vm, trit_is_trit(a) ?
                   (void*)rt_trit_new(r, rt_trit_confidence(a)) : tag_i(r)); } break;
        case SHIFT_L: b = pop(vm); a = pop(vm);
            { int r = to_int(a) << to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case SHIFT_R: b = pop(vm); a = pop(vm);
            { int r = to_int(a) >> to_int(b);
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case BIT_SET: b = pop(vm); a = pop(vm);
            { int r = to_int(a) | (1 << to_int(b));
              push(vm, tag_i(r)); } break;
        case BIT_CLR: b = pop(vm); a = pop(vm);
            { int r = to_int(a) & ~(1 << to_int(b));
              push(vm, tag_i(r)); } break;
        case BIT_TGL: b = pop(vm); a = pop(vm);
            { int r = to_int(a) ^ (1 << to_int(b));
              push(vm, tag_i(r)); } break;
        case BIT_TST: b = pop(vm); a = pop(vm);
            { int r = (to_int(a) >> to_int(b)) & 1;
              push(vm, tag_i(r)); } break;
        case LO_BYTE: a = pop(vm);
              push(vm, tag_i(to_int(a) & 0xFF)); break;
        case HI_BYTE: a = pop(vm);
              push(vm, tag_i((to_int(a) >> 8) & 0xFF)); break;
        case MRG_BYT: b = pop(vm); a = pop(vm);
              push(vm, tag_i(((to_int(a) & 0xFF) << 8) | (to_int(b) & 0xFF))); break;

        /* ── 比较（三值逻辑 + 三态传播）── */
        case EQ:  b = pop(vm); a = pop(vm);
            { int r = to_int(a) == to_int(b) ? 1 : -1;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case NE:  b = pop(vm); a = pop(vm);
            { int r = to_int(a) != to_int(b) ? 1 : -1;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case GT:  b = pop(vm); a = pop(vm);
            { int r = to_int(a) > to_int(b) ? 1 : -1;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case LT:  b = pop(vm); a = pop(vm);
            { int r = to_int(a) < to_int(b) ? 1 : -1;
              push(vm, trit_is_trit(a) || trit_is_trit(b) ?
                   (void*)rt_trit_new(r, trit_propagate_conf(a,b)/100.0) : tag_i(r)); } break;
        case GTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) >= to_int(b) ? 1 : -1)); break;
        case LTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) <= to_int(b) ? 1 : -1)); break;
        case NOT: a = pop(vm);
            { intptr_t v = to_int(a); push(vm, tag_i(v == 0 ? 0 : (v > 0 ? -1 : 1))); } break;

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
        case JMP32: {
            int32_t off = rd_i32(vm->code, &vm->pc);
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
            if (addr == 0) { push(vm, tag_i(0)); break; }  /* 未解析的 Python 辅助函数调用，压入 0 */
            if (vm->call_depth >= CALL_STACK_DEPTH) { fprintf(stderr, "调用栈溢出\n"); return 1; }
            /* 扫描函数入口连续 STORE 指令数作为参数数量。
             * ⚠ 已知限制：假设函数以 arg_count 个连续 STORE 开头。
             *   如果函数在 STORE 之间插入了其他指令，参数计数会错误。
             *   改进方向：在函数元数据中显式存储 arg_count。 */
            int32_t arg_count = 0;
            uint32_t p = (uint32_t)addr;
            while (p + 1 < vm->code_len && vm->code[p] == STORE) {
                arg_count++;
                p += 2;  /* STORE 占 2 字节 */
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
            a = pop(vm);
            if (trit_is_trit(a)) {
                rt_trit_t *t = (rt_trit_t*)a;
                printf("%d", t->value);
                if (t->confidence < 100)
                    printf("(信度:%.2f)", t->confidence / 100.0);
                printf("\n");
            } else {
                print_value(a);
                printf("\n");
            }
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
            r->h_type = OBJ_STRING;
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
                char buf[24];
                snprintf(buf, sizeof(buf), "%lld", (long long)untag_i(a));
                push(vm, tag_i((intptr_t)strlen(buf)));  /* 数字转字符串按字节计数 */
            } else push(vm, tag_i((intptr_t)utf8_char_len(rt_str_c(a))));  /* UTF-8 按字符计数 */
            break;
        }
        case STRSUB: {
            int32_t n = to_int(pop(vm));
            int32_t st = to_int(pop(vm));
            const char *s = rt_str_c(pop(vm));
            int32_t sl = (int32_t)utf8_char_len(s);               /* ⚡ 改为字符计数 */
            if (st < 0) st = 0;
            if (st > sl) st = sl;
            if (n < 0) n = 0;
            if (st + n > sl) n = sl - st;
            char *buf = utf8_substr(s, st, n);                    /* ⚡ 按字符切片 */
            push(vm, rt_str_new(buf ? buf : ""));
            free(buf);
            break;
        }
        case STREQ: {
            b = pop(vm); a = pop(vm);
            push(vm, tag_i(strcmp(rt_str_c(a), rt_str_c(b)) == 0 ? 1 : -1));
            break;
        }
        case ORD: {
            const char *s = rt_str_c(pop(vm));
            push(vm, tag_i(s[0] ? (unsigned char)s[0] : 0));
            break;
        }

        /* ── 类型检查 ── */
        case IS_NUM: push(vm, tag_i(is_int_val(pop(vm)) ? 1 : -1)); break;
        case IS_STR: push(vm, tag_i(is_str(pop(vm)) ? 1 : -1)); break;
        case IS_LIST: push(vm, tag_i(is_list(pop(vm)) ? 1 : -1)); break;
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
            int32_t n = (vm->sp > 0 && is_int_val(vm->stack[vm->sp-1])) ? to_int(pop(vm)) : 0;
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
            int32_t n = (vm->sp > 0 && is_int_val(vm->stack[vm->sp-1])) ? to_int(pop(vm)) : 0;
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
            if (is_dict(a)) {
                push(vm, tag_i(rt_dict_has((rt_dict_t*)a, k) ? 1 : -1));
            } else if (is_str(a)) {
                const char *s = rt_str_c(a);
                const char *ks = rt_str_c(k);
                push(vm, tag_i(ks[0] && strstr(s, ks) ? 1 : -1));
            } else push(vm, tag_i(-1));
            break;
        }
        case DICT_KEYS: {
            a = pop(vm);
            if (is_dict(a)) {
                rt_dict_t *d = (rt_dict_t*)a;
                rt_list_t *l = rt_list_new();
                for (int32_t i = 0; i < d->cap; i++) {
                    if (d->entries[i].k != NULL) {
                        void *k = d->entries[i].k;
                        if (is_int_val(k)) rt_list_push(l, k);
                        else rt_list_push(l, rt_str_new(rt_str_c(k)));
                    }
                }
                push(vm, l);
            } else if (is_str(a)) {
                const char *s = rt_str_c(a);
                rt_list_t *l = rt_list_new();
                while (*s) {
                    char buf[2] = {*s, 0};
                    rt_list_push(l, rt_str_new(buf));
                    s++;
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

        /* ── 模块导入：加载 .bin 文件 + 执行初始化代码 + 读取导出表 ── */
        case IMPORT: {
            const char *path = rt_str_c(pop(vm));
            if (_mod_cnt >= MOD_MAX) { push(vm, tag_i(0)); break; }
            FILE *f = fopen(path, "rb");
            if (!f) { push(vm, tag_i(0)); break; }
            /* 读取 10 字节头部：magic(4) + ver(1) + var_cnt(1) + code_size(4) */
            uint8_t hdr[10];
            if (fread(hdr, 1, 10, f) != 10 || check_bin_header(hdr, NULL)) {
                fclose(f); push(vm, tag_i(0)); break;
            }
            uint32_t sz;
            memcpy(&sz, hdr + 6, 4);
            uint8_t *code = (uint8_t*)malloc(sz);
            if (!code) { fclose(f); push(vm, tag_i(0)); break; }
            if (fread(code, 1, sz, f) != sz) {
                free(code); fclose(f); push(vm, tag_i(0)); break;
            }
            int mid = _mod_cnt;
            _mods[mid].code = code;
            _mods[mid].size = sz;
            _mods[mid].var_cnt = hdr[5];
            memset(_mods[mid].vars, 0, sizeof(void*) * VAR_MAX);
            _mods[mid].export_count = 0;
            /* 读取导出表 */
            read_export_table(f, &_mods[mid]);
            fclose(f);
            /* 执行模块初始化代码 */
            {
                VM init_vm;
                memset(&init_vm, 0, sizeof(init_vm));
                init_vm.code = code;
                init_vm.code_len = sz;
                init_vm.var_count = hdr[5];
                vm_run(&init_vm);
                memcpy(_mods[mid].vars, init_vm.vars, sizeof(void*) * VAR_MAX);
            }
            push(vm, tag_i(mid + 1));
            _mod_cnt++;
            break;
        }
        case CALL_EXT: {
            /* CALL_EXT(mod_id, func_name, arg_cnt, arg1, arg2, ...)
             * 调用已导入模块的导出函数。
             */
            int32_t mod_id = to_int(pop(vm));
            void *fname_val = pop(vm);
            const char *func_name = rt_str_c(fname_val);
            int32_t arg_cnt = to_int(pop(vm));
            void *args_stack[32];
            for (int32_t i = 0; i < arg_cnt && i < 32; i++)
                args_stack[i] = pop(vm);
            if (mod_id < 1 || mod_id > _mod_cnt) {
                push(vm, tag_i(0));
                break;
            }
            int mid = mod_id - 1;
            /* 查找导出函数地址 */
            int addr = find_export(&_mods[mid], func_name);
            if (addr < 0) {
                push(vm, tag_i(0));
                break;
            }
            /* 创建子 VM 执行函数调用 */
            VM mod_vm;
            memset(&mod_vm, 0, sizeof(mod_vm));
            mod_vm.code = _mods[mid].code;
            mod_vm.code_len = _mods[mid].size;
            mod_vm.var_count = _mods[mid].var_cnt;
            /* 复制已初始化的模块变量 */
            memcpy(mod_vm.vars, _mods[mid].vars, sizeof(void*) * VAR_MAX);
            /* args_stack: [argN(先pop), ..., arg1(后pop)] → 反转后按序压入
             * 使函数入口的 STORE 按参数顺序 pop，与 fn 编译器的循环匹配 */
            for (int32_t i = arg_cnt - 1; i >= 0; i--)
                push(&mod_vm, args_stack[i]);
            /* 设置调用帧：函数 RET 时回到 code_len 末尾 → HALT */
            mod_vm.call_stack[0].ret_pc = mod_vm.code_len;
            mod_vm.call_stack[0].stack_base = 0;
            mod_vm.call_depth = 1;
            mod_vm.pc = (uint32_t)addr;
            vm_run(&mod_vm);
            void *result = mod_vm.sp > 0 ? mod_vm.stack[mod_vm.sp - 1] : tag_i(0);
            push(vm, result);
            break;
        }

        case HALT:
            vm->halted = 1;
            break;

        /* ── 逻辑运算 ── */
        case OR: {
            b = pop(vm); a = pop(vm);
            push(vm, val_true(a) || val_true(b) ? tag_i(1) : tag_i(-1));
            break;
        }
        case AND: {
            b = pop(vm); a = pop(vm);
            push(vm, val_true(a) && val_true(b) ? tag_i(1) : tag_i(-1));
            break;
        }

        /* ── 字符串操作 ── */
        case STR_FIND: {
            /* find(haystack, needle) → index or -1 */
            b = pop(vm); a = pop(vm);
            const char *hay = rt_str_c(a);
            const char *ndl = rt_str_c(b);
            const char *pos = strstr(hay, ndl);
            push(vm, tag_i(pos ? (int32_t)(pos - hay) : -1));
            break;
        }
        case STR_TO_LIST: {
            /* str_to_list(s) → list of single-char strings */
            a = pop(vm);
            const char *s = rt_str_c(a);
            rt_list_t *l = rt_list_new();
            while (*s) {
                char ch[2] = {*s, 0};
                rt_list_push(l, rt_str_new(ch));
                s++;
            }
            push(vm, l);
            break;
        }
        case STR_STARTSWITH: {
            b = pop(vm); a = pop(vm);
            push(vm, strncmp(rt_str_c(a), rt_str_c(b), strlen(rt_str_c(b))) == 0 ? tag_i(1) : tag_i(-1));
            break;
        }
        case STR_CONTAINS: {
            b = pop(vm); a = pop(vm);
            push(vm, strstr(rt_str_c(a), rt_str_c(b)) ? tag_i(1) : tag_i(-1));
            break;
        }
        case DICT_LEN: {
            /* dict_len(d) → key count */
            a = pop(vm);
            if (is_dict(a)) {
                push(vm, tag_i(((rt_dict_t*)a)->n));
            } else {
                push(vm, tag_i(0));
            }
            break;
        }

        default:
            fprintf(stderr, "未知指令: 0x%02X @ 0x%04x\n", op, vm->pc - 1);
            return 1;
        }
    }
    return 0;
}

/* ── 加载 .bin 文件到 VM ──
 * 格式：SAN0(4) + ver(1) + var_count(1) + code_size(4) + bytecode[...] + export_table
 */
int vm_load(VM *vm, const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) { perror(path); return 1; }

    uint8_t hdr[10];
    if (fread(hdr, 1, 10, fp) != 10) { fprintf(stderr, "头部读取失败\n"); fclose(fp); return 1; }
    if (check_bin_header(hdr, path)) { fprintf(stderr, "非法固件格式\n"); fclose(fp); return 1; }

    uint8_t vc = hdr[5];
    uint32_t code_size;
    memcpy(&code_size, hdr + 6, 4);  /* 32 位代码大小 */

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

/* ── Windows 编码转换：ANSI(GBK) → UTF-8 ── */
#ifdef _WIN32
static char *ansi_to_utf8(const char *ansi) {
    int wlen = MultiByteToWideChar(CP_ACP, 0, ansi, -1, NULL, 0);
    if (wlen <= 0) return NULL;
    wchar_t *wstr = (wchar_t*)malloc((size_t)wlen * sizeof(wchar_t));
    if (!wstr) return NULL;
    MultiByteToWideChar(CP_ACP, 0, ansi, -1, wstr, wlen);
    int ulen = WideCharToMultiByte(CP_UTF8, 0, wstr, -1, NULL, 0, NULL, NULL);
    char *utf8 = (char*)malloc((size_t)ulen);
    if (!utf8) { free(wstr); return NULL; }
    WideCharToMultiByte(CP_UTF8, 0, wstr, -1, utf8, ulen, NULL, NULL);
    free(wstr);
    return utf8;
}
#endif

/* ── 从路径加载模块（代码 + 导出表 + 初始化变量）── */
static int load_module_from_path(const char *path, Module *mod) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return 1; }
    uint8_t hdr[10];
    if (fread(hdr, 1, 10, f) != 10 || check_bin_header(hdr, path)) {
        fclose(f); return 1;
    }
    uint32_t sz;
    memcpy(&sz, hdr + 6, 4);
    uint8_t *code = (uint8_t*)malloc(sz);
    if (!code) { fclose(f); return 1; }
    if (fread(code, 1, sz, f) != sz) {
        free(code); fclose(f); return 1;
    }
    memset(mod, 0, sizeof(Module));
    mod->code = code;
    mod->size = sz;
    mod->var_cnt = hdr[5];
    read_export_table(f, mod);
    fclose(f);
    /* 运行初始化代码，填充变量 */
    VM init_vm;
    memset(&init_vm, 0, sizeof(init_vm));
    init_vm.code = code;
    init_vm.code_len = sz;
    init_vm.var_count = hdr[5];
    vm_run(&init_vm);
    memcpy(mod->vars, init_vm.vars, sizeof(void*) * VAR_MAX);
    return 0;
}

/* ── 读取文件到字符串（调用者 free）── */
static char *read_file_str(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char*)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t n = fread(buf, 1, (size_t)sz, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

/* ── #include 预处理（递归展开）── */
static char *preprocess_includes_impl(const char *source, const char *base_dir, int depth);

static char *preprocess_includes(const char *source) {
    return preprocess_includes_impl(source, ".", 0);
}

static char *preprocess_includes_impl(const char *source, const char *base_dir, int depth) {
    if (depth > 10) return strdup(source);  /* 防止无限递归 */

    size_t cap = strlen(source) * 2 + 1024;
    char *result = (char*)malloc(cap);
    if (!result) return strdup(source);
    size_t pos = 0;

    const char *p = source;
    while (*p) {
        /* 检查 #include 或 ＃include */
        if ((*p == '#' || (unsigned char)*p == 0xef) &&
            strncmp(p, "#include", 8) == 0) {
            p += 8;
            /* 跳过空白 */
            while (*p == ' ' || *p == '\t') p++;
            if (*p == '"' || *p == '\'') {
                char quote = *p++;
                const char *path_start = p;
                while (*p && *p != quote) p++;
                if (*p == quote) {
                    size_t path_len = (size_t)(p - path_start);
                    p++;  /* 跳过结束引号 */

                    /* 构造完整路径 */
                    char inc_path[1024];
                    snprintf(inc_path, sizeof(inc_path), "%s/%.*s", base_dir, (int)path_len, path_start);

                    /* 读取并递归展开 */
                    char *inc_content = read_file_str(inc_path);
                    if (inc_content) {
                        /* 获取 included 文件的目录 */
                        char inc_dir[1024];
                        strncpy(inc_dir, inc_path, sizeof(inc_dir) - 1);
                        inc_dir[sizeof(inc_dir) - 1] = '\0';
                        char *slash = strrchr(inc_dir, '/');
                        if (!slash) slash = strrchr(inc_dir, '\\');
                        if (slash) *slash = '\0';
                        else strcpy(inc_dir, ".");

                        char *expanded = preprocess_includes_impl(inc_content, inc_dir, depth + 1);
                        free(inc_content);

                        if (expanded) {
                            size_t elen = strlen(expanded);
                            while (pos + elen + 1 >= cap) {
                                cap *= 2;
                                result = (char*)realloc(result, cap);
                            }
                            memcpy(result + pos, expanded, elen);
                            pos += elen;
                            free(expanded);
                        }
                        /* 跳过 #include 行的剩余部分（换行符） */
                        if (*p == '\n') p++;
                        continue;
                    } else {
                        /* 文件不存在，保留注释 */
                        const char *note = "/* #include not found */\n";
                        size_t nlen = strlen(note);
                        while (pos + nlen + 1 >= cap) { cap *= 2; result = (char*)realloc(result, cap); }
                        memcpy(result + pos, note, nlen);
                        pos += nlen;
                    }
                }
            }
            /* 跳过 #include 行的剩余部分 */
            while (*p && *p != '\n') p++;
            if (*p == '\n') p++;
            continue;
        }

        /* 普通字符 */
        result[pos++] = *p++;
        if (pos >= cap - 2) {
            cap *= 2;
            result = (char*)realloc(result, cap);
        }
    }
    result[pos] = '\0';
    return result;
}

/* ── 调用模块导出函数（单参数，返回栈顶值）── */
static void *call_module_func(Module *mod, const char *func_name, void *arg) {
    int addr = find_export(mod, func_name);
    if (addr < 0) return NULL;
    VM vm;
    memset(&vm, 0, sizeof(vm));
    vm.code = mod->code;
    vm.code_len = mod->size;
    vm.var_count = mod->var_cnt;
    memcpy(vm.vars, mod->vars, sizeof(void*) * VAR_MAX);
    if (arg) push(&vm, arg);
    vm.call_stack[0].ret_pc = vm.code_len;
    vm.call_stack[0].stack_base = 0;
    vm.call_depth = 1;
        vm.call_stack[0].ret_pc = vm.code_len;
        vm.call_stack[0].stack_base = 0;
        vm.call_depth = 1;
        vm.pc = (uint32_t)addr;
        vm_run(&vm);
    return vm.sp > 0 ? vm.stack[vm.sp - 1] : NULL;
}

/* ── 运行外部工具（返回 0 表示成功）── */
static int run_cmd(const char *cmd) {
#ifdef _WIN32
    /* Windows: 重定向 stderr 到 nul 避免干扰输出 */
    char buf[1024];
    snprintf(buf, sizeof(buf), "%s 2>nul", cmd);
    return system(buf);
#else
    char buf[1024];
    snprintf(buf, sizeof(buf), "%s 2>/dev/null", cmd);
    return system(buf);
#endif
}

/* ── 查找工具路径（返回静态缓冲区或 NULL）── */
static const char *find_tool(const char *name) {
    static char buf[512];
    /* 直接检查文件是否存在 */
    snprintf(buf, sizeof(buf), "%s.exe", name);
    FILE *f = fopen(buf, "rb");
    if (f) { fclose(f); return buf; }
    snprintf(buf, sizeof(buf), "%s", name);
    f = fopen(buf, "rb");
    if (f) { fclose(f); return buf; }
#ifdef _WIN32
    const char *dirs[] = {
        "D:\\msys64\\ucrt64\\bin",
        "D:\\msys64\\mingw64\\bin",
        NULL
    };
    for (int i = 0; dirs[i]; i++) {
        snprintf(buf, sizeof(buf), "%s\\%s.exe", dirs[i], name);
        f = fopen(buf, "rb");
        if (f) { fclose(f); return buf; }
        snprintf(buf, sizeof(buf), "%s\\%s", dirs[i], name);
        f = fopen(buf, "rb");
        if (f) { fclose(f); return buf; }
    }
#endif
    /* 最后假设在 PATH 中 */
    snprintf(buf, sizeof(buf), "%s", name);
    return buf;
}

/* ── 主入口 ── */
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "用法: %s firmware.bin [--run] [源码文件]\n", argv[0]);
        fprintf(stderr, "      %s --call module.bin 函数名 [参数...]\n", argv[0]);
        fprintf(stderr, "      %s --compile input.san [-o output.exe]\n", argv[0]);
        return 1;
    }

    vm_register_device(0, mock_sensor_read, NULL);
    vm_register_device(1, NULL, mock_actuator_write);

    /* --call 模式：直接调用模块的导出函数 */
    if (strcmp(argv[1], "--call") == 0) {
        if (argc < 4) {
            fprintf(stderr, "用法: %s --call module.bin 函数名 [参数...]\n", argv[0]);
            return 1;
        }
        const char *mod_path = argv[2];
        const char *func_name = argv[3];
#ifdef _WIN32
        char *utf8_name = ansi_to_utf8(func_name);
#endif

        Module mod;
        if (load_module_from_path(mod_path, &mod)) return 1;

        /* 查找函数：先用原名，失败则用 ANSI→UTF-8 转换后的名称 */
        int addr = find_export(&mod, func_name);
#ifdef _WIN32
        if (addr < 0 && utf8_name) {
            addr = find_export(&mod, utf8_name);
            if (addr >= 0) func_name = utf8_name;
        }
#endif
        if (addr < 0) {
            fprintf(stderr, "未找到导出函数: %s\n", func_name);
#ifdef _WIN32
            free(utf8_name);
#endif
            return 1;
        }
#ifdef _WIN32
        free(utf8_name);
#endif

        /* 压入参数（字符串或整数） */
        VM call_vm;
        memset(&call_vm, 0, sizeof(call_vm));
        call_vm.code = mod.code;
        call_vm.code_len = mod.size;
        call_vm.var_count = mod.var_cnt;
        memcpy(call_vm.vars, mod.vars, sizeof(void*) * VAR_MAX);
        for (int i = 4; i < argc; i++) {
            char *end = NULL;
            long val = strtol(argv[i], &end, 10);
            if (*end == '\0') {
                push(&call_vm, tag_i((int32_t)val));
            } else {
                push(&call_vm, rt_str_new(argv[i]));
            }
        }

        /* 设置调用帧 */
        call_vm.call_stack[0].ret_pc = call_vm.code_len;
        call_vm.call_stack[0].stack_base = 0;
        call_vm.call_depth = 1;
        call_vm.pc = (uint32_t)addr;
        vm_run(&call_vm);

        /* 输出返回值 */
        if (call_vm.sp > 0) {
            print_value(call_vm.stack[call_vm.sp - 1]);
            printf("\n");
        }

        free((void*)mod.code);
        return 0;
    }

    /* --compile 模式：完整编译管线（无 Python 依赖）
     * 用法: runtime.exe --compile input.san [-o output.exe]
     *       [--sugar stdlib/sugar.bin] [--llvmgen stdlib/llvmgen.bin]
     * 管线: source.san → sugar.bin[解析] → AST → llvmgen.bin[编译顶层] → IR → llc → gcc → exe
     */
    if (strcmp(argv[1], "--compile") == 0) {
        if (argc < 3) {
            fprintf(stderr, "用法: %s --compile input.san [-o output.exe]\n", argv[0]);
            return 1;
        }
        const char *input_path = argv[2];
        const char *output_path = "output.exe";
        const char *sugar_path = "stdlib/sugar.bin";
        const char *llvmgen_path = "stdlib/llvmgen.bin";

        /* 解析可选参数 */
        for (int i = 3; i < argc; i++) {
            if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
                output_path = argv[++i];
            } else if (strcmp(argv[i], "--sugar") == 0 && i + 1 < argc) {
                sugar_path = argv[++i];
            } else if (strcmp(argv[i], "--llvmgen") == 0 && i + 1 < argc) {
                llvmgen_path = argv[++i];
            }
        }

        fprintf(stderr, "[编译] %s → %s\n", input_path, output_path);

        /* 1. 读取源码 + #include 展开 */
        char *raw_source = read_file_str(input_path);
        if (!raw_source) {
            fprintf(stderr, "错误: 无法读取 %s\n", input_path);
            return 1;
        }
        char *source = preprocess_includes(raw_source);
        free(raw_source);
        fprintf(stderr, "[1/5] 源码 %ld 字节（含 #include 展开）\n", (long)strlen(source));

        /* 2. 加载 sugar.bin 并调用 解析(source) → AST */
        Module sugar_mod;
        if (load_module_from_path(sugar_path, &sugar_mod)) {
            fprintf(stderr, "错误: 无法加载 %s\n", sugar_path);
            free(source);
            return 1;
        }
        void *ast = call_module_func(&sugar_mod, "解析", rt_str_new(source));
        free(source);
        if (!ast) {
            fprintf(stderr, "错误: sugar.bin 解析失败（未返回结果）\n");
            free((void*)sugar_mod.code);
            return 1;
        }
        fprintf(stderr, "[2/5] 解析完成\n");

        /* 3. 加载 llvmgen.bin 并调用 编译顶层(ast) → IR */
        Module llvmgen_mod;
        if (load_module_from_path(llvmgen_path, &llvmgen_mod)) {
            fprintf(stderr, "错误: 无法加载 %s\n", llvmgen_path);
            free((void*)sugar_mod.code);
            return 1;
        }
        void *ir_val = call_module_func(&llvmgen_mod, "编译顶层", ast);
        if (!ir_val || !is_str(ir_val)) {
            fprintf(stderr, "错误: llvmgen.bin 编译顶层未返回字符串\n");
            free((void*)sugar_mod.code);
            free((void*)llvmgen_mod.code);
            return 1;
        }
        const char *ir_text = rt_str_c(ir_val);
        fprintf(stderr, "[3/5] IR 生成 %ld 字节\n", (long)strlen(ir_text));

        /* 4. 如果 IR 为空，无法继续编译 */
        if (strlen(ir_text) == 0) {
            fprintf(stderr, "提示: IR 为空（llvmgen.bin 缺少 Python 辅助函数）\n");
            fprintf(stderr, "请使用 main.py --san 完成 LLVM 编译\n");
            free((void*)sugar_mod.code);
            free((void*)llvmgen_mod.code);
            return 1;
        }

        /* 5. 创建 build 目录并写入 .ll 文件 */
#ifdef _WIN32
        _mkdir("build");
#else
        mkdir("build", 0755);
#endif
        char ll_path[260], o_path[260];
        snprintf(ll_path, sizeof(ll_path), "build/_cvm_compile.ll");
        snprintf(o_path, sizeof(o_path), "build/_cvm_compile.o");
        {
            FILE *f = fopen(ll_path, "w");
            if (!f) {
                fprintf(stderr, "错误: 无法创建 %s\n", ll_path);
                free((void*)sugar_mod.code);
                free((void*)llvmgen_mod.code);
                return 1;
            }
            fwrite(ir_text, 1, strlen(ir_text), f);
            fclose(f);
        }

        /* 5. IR → 目标文件（优先 llc，回退 clang） */
        const char *llc = find_tool("llc");
        const char *clang = llc ? NULL : find_tool("clang");
        int obj_ok = 0;
        if (llc) {
            char cmd[1024];
            snprintf(cmd, sizeof(cmd), "%s -filetype=obj %s -o %s", llc, ll_path, o_path);
            fprintf(stderr, "[4/5] llc → .o\n");
            obj_ok = (run_cmd(cmd) == 0);
        }
        if (!obj_ok && clang) {
            char cmd[1024];
            snprintf(cmd, sizeof(cmd), "%s -c %s -o %s", clang, ll_path, o_path);
            fprintf(stderr, "[4/5] clang → .o\n");
            obj_ok = (run_cmd(cmd) == 0);
        }
        if (!obj_ok) {
            fprintf(stderr, "错误: 无法编译 IR（需要 llc 或 clang）\n");
            free((void*)sugar_mod.code);
            free((void*)llvmgen_mod.code);
            remove(ll_path);
            return 1;
        }

        /* 6. 目标文件 → 可执行文件（gcc 链接） */
        const char *gcc = find_tool("gcc");
        if (!gcc) {
            fprintf(stderr, "错误: 需要 gcc\n");
            free((void*)sugar_mod.code);
            free((void*)llvmgen_mod.code);
            remove(ll_path);
            remove(o_path);
            return 1;
        }
        {
            char cmd[768];
            /* 检查 llvmgen/runtime.c 是否存在 */
            FILE *rc = fopen("llvmgen/runtime.c", "r");
            if (rc) {
                fclose(rc);
                snprintf(cmd, sizeof(cmd), "%s %s llvmgen/runtime.c -o %s -lm",
                         gcc, o_path, output_path);
            } else {
                snprintf(cmd, sizeof(cmd), "%s %s -o %s -lm",
                         gcc, o_path, output_path);
            }
            fprintf(stderr, "[5/5] gcc → %s\n", output_path);
            obj_ok = (run_cmd(cmd) == 0);
        }

        /* 清理临时文件 */
        remove(ll_path);
        remove(o_path);
        free((void*)sugar_mod.code);
        free((void*)llvmgen_mod.code);

        if (obj_ok) {
            fprintf(stderr, "[完成] %s\n", output_path);
            return 0;
        } else {
            fprintf(stderr, "错误: 链接失败\n");
            return 1;
        }
    }

    VM vm;
    if (vm_load(&vm, argv[1])) return 1;

    /* 如果提供了源码文件，将其路径存入变量 0 */
    if (argc > 2 && strcmp(argv[2], "--run") != 0) {
        vm.vars[0] = rt_str_new(argv[2]);
        vm.var_count = 1;
    }

    int ret = vm_run(&vm);

    /* --run 模式：输出栈顶值（用于管线） */
    if (argc > 2 && strcmp(argv[2], "--run") == 0) {
        if (vm.sp > 0) {
            print_value(vm.stack[vm.sp - 1]);
            printf("\n");
        }
    }

    free((void*)vm.code);
    return ret;
}
