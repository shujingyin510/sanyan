/**
 * test_runtime.c — C VM 单元测试
 *
 * 测试覆盖:
 *   1. 标记指针 (tag_i, untag_i, is_int_val, to_int)
 *   2. 字符串 (rt_str_new, rt_str_c)
 *   3. 列表 (rt_list_new, rt_list_push)
 *   4. 字典 (rt_dict_new, rt_dict_set, rt_dict_get, rt_dict_has)
 *   5. 字节码执行: 算术、比较、变量、控制流、字符串、列表、字典、函数调用
 *
 * 编译: gcc -o test_runtime test_runtime.c -std=c99 -Wall
 * 运行: ./test_runtime
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── 从 runtime.c 提取的类型和函数 ── */
/* 因为 runtime.c 中的函数是 static，需要重新定义 */

#define VAR_MAX 256
#define STACK_MAX 512
#define CALL_STACK_DEPTH 64
#define NATIVE_DEV_MAX 16
#define DICT_INIT_CAP 16
#define MOD_MAX 16

typedef enum { TYPE_STR = 0x535452, TYPE_LIST = 0x4C4953, TYPE_DICT = 0x444943 } ObjType;
#define OBJ_HDR ObjType type

/* ── 指令码 ── */
typedef enum {
    NOP=0x00, PUSH_I=0x01, ADD=0x02, SUB=0x03, MUL=0x04, DIV=0x05, MOD=0x06,
    LOAD=0x07, STORE=0x08, JMP=0x09, JZ=0x0A, JNZ=0x0B, CALL=0x0C, RET=0x0D,
    PRINT=0x0E, IO_READ=0x0F, IO_WRITE=0x10, EQ=0x11, NE=0x12, GT=0x13, LT=0x14,
    GTE=0x15, LTE=0x16, NOT=0x17, WAIT=0x18, CONCAT=0x19, STRLEN=0x1A, STRSUB=0x1B,
    STREQ=0x1C, DICT=0x1D, DICT_GET=0x1E, DICT_SET=0x1F, DICT_HAS=0x20,
    IS_NUM=0x21, IS_STR=0x22, IS_LIST=0x23, SAME=0x24, GET=0x25, SET_ELEM=0x26,
    LIST_NEW=0x27, LIST_CCAT=0x28, SLICE=0x29, LIST_LEN=0x2A, READ_FILE=0x2B,
    WRITE_FILE=0x2C, PUSH_STR=0x2D, IMPORT=0x2E, CALL_EXT=0x2F, WRITE_BIN=0x30,
    ORD=0x31, DICT_KEYS=0x32, JMP32=0x33, HALT=0xFF,
} Opcode;

/* ── 标记指针 ── */
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

/* ── 字符串 ── */
typedef struct { OBJ_HDR; int32_t len; char data[]; } rt_str_t;
static rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t n = (int32_t)strlen(s);
    rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + n + 1);
    if (!r) return NULL;
    r->type = TYPE_STR; r->len = n;
    memcpy(r->data, s, n + 1);
    return r;
}
static const char *rt_str_c(void *p) {
    if (!p || is_int_val(p)) return "";
    return ((rt_str_t*)p)->data;
}

/* ── 列表 ── */
typedef struct { OBJ_HDR; int32_t len; int32_t cap; void **items; } rt_list_t;
static rt_list_t *rt_list_new(void) {
    rt_list_t *l = (rt_list_t*)calloc(1, sizeof(rt_list_t));
    if (!l) return NULL;
    l->type = TYPE_LIST; l->cap = 4;
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

/* ── 字典（哈希表：开放寻址 + 线性探测）── */
#define DICT_LOAD_FACTOR 70
typedef struct { void *k; void *v; } rt_entry_t;
typedef struct { OBJ_HDR; int32_t n; int32_t cap; rt_entry_t *entries; } rt_dict_t;
static uint32_t hash_key(void *k) {
    if (is_int_val(k)) {
        uint32_t h = (uint32_t)untag_i(k);
        h = ((h >> 16) ^ h) * 0x45d9f3b;
        h = ((h >> 16) ^ h) * 0x45d9f3b;
        return (h >> 16) ^ h;
    }
    const char *s = rt_str_c(k);
    uint32_t h = 5381;
    while (*s) h = ((h << 5) + h) + (unsigned char)*s++;
    return h;
}
static int key_eq(void *a, void *b) {
    if (is_int_val(a) && is_int_val(b)) return untag_i(a) == untag_i(b);
    if (!is_int_val(a) && !is_int_val(b) && a && b)
        return strcmp(((rt_str_t*)a)->data, ((rt_str_t*)b)->data) == 0;
    return a == b;
}
static void rt_dict_rehash(rt_dict_t *d) {
    int32_t old_cap = d->cap;
    rt_entry_t *old = d->entries;
    d->cap = old_cap * 2;
    d->entries = (rt_entry_t*)calloc((size_t)d->cap, sizeof(rt_entry_t));
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
    d->type = TYPE_DICT; d->cap = DICT_INIT_CAP;
    d->entries = (rt_entry_t*)calloc(DICT_INIT_CAP, sizeof(rt_entry_t));
    return d;
}
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
    if (d->n >= (d->cap * DICT_LOAD_FACTOR) / 100)
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

/* ── 类型检查 ── */
static int is_obj_type(void *p, ObjType t) {
    return p && !is_int_val(p) && ((rt_str_t*)p)->type == t;
}
static int is_str(void *p)  { return is_obj_type(p, TYPE_STR); }
static int is_list(void *p) { return is_obj_type(p, TYPE_LIST); }
static int is_dict(void *p) { return is_obj_type(p, TYPE_DICT); }

/* ── VM ── */
typedef struct {
    uint32_t ret_pc; int16_t stack_base;
    void *saved_vars[VAR_MAX]; uint8_t saved_var_cnt;
} CallFrame;

typedef struct {
    void *stack[STACK_MAX]; int16_t sp;
    void *vars[VAR_MAX]; uint8_t var_count;
    const uint8_t *code; uint32_t code_len; uint32_t pc;
    CallFrame call_stack[CALL_STACK_DEPTH]; uint8_t call_depth;
    int halted;
} VM;

static void push(VM *vm, void *v) {
    if (vm->sp >= STACK_MAX) { fprintf(stderr, "栈溢出\n"); exit(1); }
    vm->stack[vm->sp++] = v;
}
static void *pop(VM *vm) {
    if (vm->sp <= 0) { fprintf(stderr, "栈下溢\n"); exit(1); }
    return vm->stack[--vm->sp];
}
static uint8_t rd_u8(const uint8_t *c, uint32_t *pc) { return c[(*pc)++]; }
static int32_t rd_i32(const uint8_t *c, uint32_t *pc) {
    int32_t v; memcpy(&v, c + *pc, 4); *pc += 4; return v;
}
static int16_t rd_i16(const uint8_t *c, uint32_t *pc) {
    int16_t v; memcpy(&v, c + *pc, 2); *pc += 2; return v;
}
static int val_true(void *v) {
    if (is_int_val(v)) return untag_i(v) != 0;
    return v != NULL;
}

static struct { void *code; uint32_t size; uint8_t var_cnt; void *vars[VAR_MAX]; } _mods[MOD_MAX];
static int _mod_cnt;

/* ── 原生设备（测试用） ── */
static int32_t mock_read(uint8_t id) { (void)id; return 42; }
static void mock_write(uint8_t id, int32_t val) { (void)id; (void)val; }

typedef int32_t (*native_read_fn)(uint8_t);
typedef void (*native_write_fn)(uint8_t, int32_t);
typedef struct { native_read_fn read; native_write_fn write; } NativeDevice;
static NativeDevice _devs[NATIVE_DEV_MAX];

static void vm_register_device(uint8_t id, native_read_fn r, native_write_fn w) {
    if (id < NATIVE_DEV_MAX) _devs[id] = (NativeDevice){r, w};
}

/* ═══════════════════════════════════════════════════
 * vm_run — 从 runtime.c 复制的核心解释循环
 * ═══════════════════════════════════════════════════ */
static int vm_run(VM *vm) {
    while (!vm->halted) {
        if (vm->pc >= vm->code_len) { vm->halted = 1; break; }
        uint8_t op = rd_u8(vm->code, &vm->pc);
        void *a, *b;
        switch (op) {
        case NOP: break;
        case PUSH_I: push(vm, tag_i(rd_i32(vm->code, &vm->pc))); break;
        case ADD: b = pop(vm); a = pop(vm); push(vm, tag_i(to_int(a) + to_int(b))); break;
        case SUB: b = pop(vm); a = pop(vm); push(vm, tag_i(to_int(a) - to_int(b))); break;
        case MUL: b = pop(vm); a = pop(vm); push(vm, tag_i(to_int(a) * to_int(b))); break;
        case DIV: b = pop(vm); a = pop(vm);
            push(vm, to_int(b) != 0 ? tag_i(to_int(a) / to_int(b)) : tag_i(0)); break;
        case MOD: b = pop(vm); a = pop(vm);
            push(vm, to_int(b) != 0 ? tag_i(to_int(a) % to_int(b)) : tag_i(0)); break;
        case LOAD: { uint8_t idx = rd_u8(vm->code, &vm->pc);
            push(vm, idx < vm->var_count ? vm->vars[idx] : tag_i(0)); break; }
        case STORE: { uint8_t idx = rd_u8(vm->code, &vm->pc);
            vm->vars[idx] = pop(vm); if (idx >= vm->var_count) vm->var_count = idx + 1; break; }
        case JMP: vm->pc = (uint32_t)rd_i32(vm->code, &vm->pc); break;
        case JZ: { int32_t tgt = rd_i32(vm->code, &vm->pc);
            if (!val_true(pop(vm))) vm->pc = (uint32_t)tgt; break; }
        case JNZ: { int32_t tgt = rd_i32(vm->code, &vm->pc);
            if (val_true(pop(vm))) vm->pc = (uint32_t)tgt; break; }
        case CALL: {
            uint8_t argc = rd_u8(vm->code, &vm->pc);
            int32_t tgt = rd_i32(vm->code, &vm->pc);
            if (vm->call_depth >= CALL_STACK_DEPTH) { fprintf(stderr, "调用栈溢出\n"); return 1; }
            CallFrame *f = &vm->call_stack[vm->call_depth++];
            f->ret_pc = vm->pc; f->stack_base = vm->sp - argc;
            f->saved_var_cnt = vm->var_count;
            memcpy(f->saved_vars, vm->vars, sizeof(void*) * vm->var_count);
            vm->pc = (uint32_t)tgt;
            break; }
        case RET: {
            if (vm->call_depth == 0) { vm->halted = 1; break; }
            CallFrame *f = &vm->call_stack[--vm->call_depth];
            void *result = vm->sp > f->stack_base ? vm->stack[vm->sp - 1] : tag_i(0);
            vm->sp = f->stack_base;
            vm->pc = f->ret_pc;
            vm->var_count = f->saved_var_cnt;
            memcpy(vm->vars, f->saved_vars, sizeof(void*) * vm->var_count);
            push(vm, result);
            break; }
        case EQ: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) == to_int(b) ? 1 : -1)); break;
        case NE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) != to_int(b) ? 1 : -1)); break;
        case GT: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) > to_int(b) ? 1 : -1)); break;
        case LT: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) < to_int(b) ? 1 : -1)); break;
        case GTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) >= to_int(b) ? 1 : -1)); break;
        case LTE: b = pop(vm); a = pop(vm);
            push(vm, tag_i(to_int(a) <= to_int(b) ? 1 : -1)); break;
        case NOT: a = pop(vm); push(vm, tag_i(val_true(a) ? -1 : 1)); break;
        case PUSH_STR: {
            uint16_t len = (uint16_t)rd_u8(vm->code, &vm->pc);
            len |= (uint16_t)rd_u8(vm->code, &vm->pc) << 8;
            rt_str_t *s = (rt_str_t*)malloc(sizeof(rt_str_t) + len + 1);
            s->type = TYPE_STR; s->len = (int32_t)len;
            memcpy(s->data, vm->code + vm->pc, len);
            s->data[len] = '\0'; vm->pc += len;
            push(vm, s);
            break; }
        case CONCAT: {
            a = pop(vm); b = pop(vm);
            const char *sa = rt_str_c(a), *sb = rt_str_c(b);
            int32_t la = is_str(a) ? ((rt_str_t*)a)->len : (int32_t)strlen(sa);
            int32_t lb = is_str(b) ? ((rt_str_t*)b)->len : (int32_t)strlen(sb);
            rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + la + lb + 1);
            r->type = TYPE_STR; r->len = la + lb;
            memcpy(r->data, sb, lb); memcpy(r->data + lb, sa, la);
            r->data[la + lb] = '\0'; push(vm, r);
            break; }
        case STRLEN: a = pop(vm);
            push(vm, tag_i(is_str(a) ? ((rt_str_t*)a)->len : 0)); break;
        case HALT: vm->halted = 1; break;
        case PRINT: a = pop(vm);
            if (is_int_val(a)) printf("%d", untag_i(a));
            else if (is_str(a)) printf("%s", ((rt_str_t*)a)->data);
            else if (is_list(a)) { rt_list_t *l = (rt_list_t*)a;
                printf("["); for (int32_t i = 0; i < l->len; i++) {
                    if (i) printf(", "); if (is_int_val(l->items[i])) printf("%d", untag_i(l->items[i]));
                    else if (is_str(l->items[i])) printf("%s", ((rt_str_t*)l->items[i])->data);
                } printf("]"); }
            printf("\n"); break;
        case IS_NUM: a = pop(vm); push(vm, tag_i(is_int_val(a) ? 1 : -1)); break;
        case IS_STR: a = pop(vm); push(vm, tag_i(is_str(a) ? 1 : -1)); break;
        case IS_LIST: a = pop(vm); push(vm, tag_i(is_list(a) ? 1 : -1)); break;
        case SAME: b = pop(vm); a = pop(vm); push(vm, tag_i(a == b ? 1 : -1)); break;
        case LIST_NEW: { uint8_t cnt = rd_u8(vm->code, &vm->pc);
            rt_list_t *l = rt_list_new();
            for (int i = 0; i < cnt; i++) { void *v = pop(vm); l->items[l->len++] = v; }
            /* reverse since items were pushed in reverse */
            for (int i = 0; i < l->len / 2; i++) {
                void *tmp = l->items[i]; l->items[i] = l->items[l->len - 1 - i];
                l->items[l->len - 1 - i] = tmp; }
            push(vm, l); break; }
        case GET: { int32_t idx = to_int(pop(vm)); a = pop(vm);
            if (is_list(a)) { rt_list_t *l = (rt_list_t*)a;
                push(vm, (idx >= 0 && idx < l->len) ? l->items[idx] : tag_i(0)); }
            else push(vm, tag_i(0)); break; }
        case LIST_LEN: a = pop(vm);
            push(vm, tag_i(is_list(a) ? ((rt_list_t*)a)->len : 0)); break;
        case LIST_CCAT: { b = pop(vm); a = pop(vm);
            if (is_list(a) && is_list(b)) {
                rt_list_t *r = rt_list_new();
                for (int32_t i = 0; i < ((rt_list_t*)b)->len; i++)
                    rt_list_push(r, ((rt_list_t*)b)->items[i]);
                for (int32_t i = 0; i < ((rt_list_t*)a)->len; i++)
                    rt_list_push(r, ((rt_list_t*)a)->items[i]);
                push(vm, r);
            } else push(vm, tag_i(0)); break; }
        case SLICE: { int32_t end = to_int(pop(vm)); int32_t start = to_int(pop(vm));
            a = pop(vm);
            if (is_list(a)) { rt_list_t *l = (rt_list_t*)a; rt_list_t *r = rt_list_new();
                for (int32_t i = start; i < end && i < l->len; i++) rt_list_push(r, l->items[i]);
                push(vm, r); } else push(vm, tag_i(0)); break; }
        case DICT: { uint8_t cnt = rd_u8(vm->code, &vm->pc);
            rt_dict_t *d = rt_dict_new();
            for (int i = 0; i < cnt; i++) { void *v = pop(vm); void *k = pop(vm);
                rt_dict_set(d, k, v); }
            push(vm, d); break; }
        case DICT_GET: { a = pop(vm); b = pop(vm);
            if (is_dict(b)) push(vm, rt_dict_get((rt_dict_t*)b, a));
            else push(vm, tag_i(0)); break; }
        case DICT_SET: { a = pop(vm); b = pop(vm); void *c = pop(vm);
            if (is_dict(c)) rt_dict_set((rt_dict_t*)c, b, a);
            push(vm, a); break; }
        case DICT_HAS: { a = pop(vm); b = pop(vm);
            if (is_dict(b)) push(vm, tag_i(rt_dict_has((rt_dict_t*)b, a) ? 1 : -1));
            else push(vm, tag_i(-1)); break; }
        case WAIT: a = pop(vm); (void)a; break;
        case IO_READ: { uint8_t dev = rd_u8(vm->code, &vm->pc);
            push(vm, tag_i(_devs[dev].read ? _devs[dev].read(dev) : 0)); break; }
        case IO_WRITE: { uint8_t dev = rd_u8(vm->code, &vm->pc);
            a = pop(vm); if (_devs[dev].write) _devs[dev].write(dev, to_int(a)); break; }
        case ORD: a = pop(vm);
            push(vm, tag_i(is_str(a) && ((rt_str_t*)a)->len > 0 ?
                (unsigned char)((rt_str_t*)a)->data[0] : 0)); break;
        case SET_ELEM: { int32_t idx = to_int(pop(vm)); a = pop(vm); b = pop(vm);
            if (is_list(b) && idx >= 0 && idx < ((rt_list_t*)b)->len)
                ((rt_list_t*)b)->items[idx] = a;
            push(vm, a); break; }
        case DICT_KEYS: { a = pop(vm);
            if (is_dict(a)) { rt_dict_t *d = (rt_dict_t*)a; rt_list_t *l = rt_list_new();
                for (int32_t i = 0; i < d->cap; i++)
                    if (d->entries[i].k != NULL) rt_list_push(l, d->entries[i].k);
                push(vm, l); } else push(vm, tag_i(0)); break; }
        case STREQ: { b = pop(vm); a = pop(vm);
            push(vm, tag_i(strcmp(rt_str_c(a), rt_str_c(b)) == 0 ? 1 : -1)); break; }
        default:
            fprintf(stderr, "未知指令: 0x%02X @ 0x%04x\n", op, vm->pc - 1);
            return 1;
        }
    }
    return 0;
}

/* ═══════════════════════════════════════════════════
 * 测试框架
 * ═══════════════════════════════════════════════════ */
static int _tests_run = 0, _tests_passed = 0, _tests_failed = 0;

#define ASSERT(expr, msg) do { \
    _tests_run++; \
    if (expr) { _tests_passed++; } \
    else { _tests_failed++; fprintf(stderr, "  FAIL: %s (line %d)\n", msg, __LINE__); } \
} while(0)

#define ASSERT_EQ_INT(got, expected, msg) do { \
    _tests_run++; \
    if ((got) == (expected)) { _tests_passed++; } \
    else { _tests_failed++; fprintf(stderr, "  FAIL: %s — got %d, expected %d (line %d)\n", msg, (int)(got), (int)(expected), __LINE__); } \
} while(0)

#define ASSERT_EQ_STR(got, expected, msg) do { \
    _tests_run++; \
    if (strcmp((got), (expected)) == 0) { _tests_passed++; } \
    else { _tests_failed++; fprintf(stderr, "  FAIL: %s — got \"%s\", expected \"%s\" (line %d)\n", msg, (got), (expected), __LINE__); } \
} while(0)

/* ── 辅助：创建 VM 并运行字节码 ── */
static int run_bytes(VM *vm, const uint8_t *code, uint32_t len) {
    memset(vm, 0, sizeof(*vm));
    vm->code = code;
    vm->code_len = len;
    vm->var_count = 0;
    return vm_run(vm);
}

/* ═══════════════════════════════════════════════════
 * 测试用例
 * ═══════════════════════════════════════════════════ */

/* ── 1. 标记指针 ── */
void test_tagged_integers(void) {
    printf("  test_tagged_integers...\n");
    ASSERT(is_int_val(tag_i(0)), "tag_i(0) is int");
    ASSERT(is_int_val(tag_i(42)), "tag_i(42) is int");
    ASSERT(is_int_val(tag_i(-1)), "tag_i(-1) is int");
    ASSERT(!is_int_val(tag_i(0) + 1), "non-tagged is not int");
    ASSERT_EQ_INT(untag_i(tag_i(0)), 0, "untag 0");
    ASSERT_EQ_INT(untag_i(tag_i(42)), 42, "untag 42");
    ASSERT_EQ_INT(untag_i(tag_i(-1)), -1, "untag -1");
    ASSERT_EQ_INT(to_int(tag_i(99)), 99, "to_int tagged");
    ASSERT_EQ_INT(to_int(NULL), 0, "to_int NULL");
}

/* ── 2. 字符串 ── */
void test_strings(void) {
    printf("  test_strings...\n");
    rt_str_t *s = rt_str_new("hello");
    ASSERT(s != NULL, "rt_str_new not NULL");
    ASSERT(is_str(s), "is_str");
    ASSERT_EQ_INT(s->len, 5, "string length");
    ASSERT_EQ_STR(rt_str_c(s), "hello", "string data");
    ASSERT_EQ_STR(rt_str_c(NULL), "", "rt_str_c NULL");
    ASSERT_EQ_STR(rt_str_c(tag_i(42)), "", "rt_str_c int");
    free(s);
}

/* ── 3. 列表 ── */
void test_lists(void) {
    printf("  test_lists...\n");
    rt_list_t *l = rt_list_new();
    ASSERT(l != NULL, "rt_list_new not NULL");
    ASSERT(is_list(l), "is_list");
    ASSERT_EQ_INT(l->len, 0, "empty list len");
    rt_list_push(l, tag_i(10));
    rt_list_push(l, tag_i(20));
    ASSERT_EQ_INT(l->len, 2, "list len after push");
    ASSERT_EQ_INT(to_int(l->items[0]), 10, "list item 0");
    ASSERT_EQ_INT(to_int(l->items[1]), 20, "list item 1");
    free(l->items); free(l);
}

/* ── 4. 字典 ── */
void test_dicts(void) {
    printf("  test_dicts...\n");
    rt_dict_t *d = rt_dict_new();
    ASSERT(d != NULL, "rt_dict_new not NULL");
    ASSERT(is_dict(d), "is_dict");
    rt_dict_set(d, tag_i(1), tag_i(100));
    rt_dict_set(d, rt_str_new("key"), tag_i(200));
    ASSERT_EQ_INT(rt_dict_has(d, tag_i(1)), 1, "dict has int key");
    ASSERT_EQ_INT(rt_dict_has(d, tag_i(99)), 0, "dict missing key");
    ASSERT_EQ_INT(to_int(rt_dict_get(d, tag_i(1))), 100, "dict get int key");
    ASSERT_EQ_INT(to_int(rt_dict_get(d, rt_str_new("key"))), 200, "dict get str key");
    ASSERT_EQ_INT(to_int(rt_dict_get(d, tag_i(99))), 0, "dict get missing");
    /* overwrite */
    rt_dict_set(d, tag_i(1), tag_i(999));
    ASSERT_EQ_INT(to_int(rt_dict_get(d, tag_i(1))), 999, "dict overwrite");
    free(d->entries); free(d);
}

/* ── 5. 字节码: 算术 ── */
void test_vm_arithmetic(void) {
    printf("  test_vm_arithmetic...\n");
    VM vm;
    /* PUSH_I 7, PUSH_I 3, ADD, HALT → stack top = 10 */
    uint8_t code1[] = { PUSH_I, 7,0,0,0, PUSH_I, 3,0,0,0, ADD, HALT };
    run_bytes(&vm, code1, sizeof(code1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 10, "7 + 3");
    /* SUB */
    uint8_t code2[] = { PUSH_I, 10,0,0,0, PUSH_I, 4,0,0,0, SUB, HALT };
    run_bytes(&vm, code2, sizeof(code2));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 6, "10 - 4");
    /* MUL */
    uint8_t code3[] = { PUSH_I, 6,0,0,0, PUSH_I, 7,0,0,0, MUL, HALT };
    run_bytes(&vm, code3, sizeof(code3));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 42, "6 * 7");
    /* DIV */
    uint8_t code4[] = { PUSH_I, 20,0,0,0, PUSH_I, 4,0,0,0, DIV, HALT };
    run_bytes(&vm, code4, sizeof(code4));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 5, "20 / 4");
    /* MOD */
    uint8_t code5[] = { PUSH_I, 17,0,0,0, PUSH_I, 5,0,0,0, MOD, HALT };
    run_bytes(&vm, code5, sizeof(code5));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 2, "17 % 5");
    /* DIV by zero → 0 */
    uint8_t code6[] = { PUSH_I, 10,0,0,0, PUSH_I, 0,0,0,0, DIV, HALT };
    run_bytes(&vm, code6, sizeof(code6));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 0, "10 / 0 = 0");
}

/* ── 6. 字节码: 比较 ── */
void test_vm_comparison(void) {
    printf("  test_vm_comparison...\n");
    VM vm;
    /* EQ: 5 == 5 → 1 */
    uint8_t c1[] = { PUSH_I, 5,0,0,0, PUSH_I, 5,0,0,0, EQ, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "5 == 5");
    /* NE: 5 != 3 → 1 */
    uint8_t c2[] = { PUSH_I, 5,0,0,0, PUSH_I, 3,0,0,0, NE, HALT };
    run_bytes(&vm, c2, sizeof(c2));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "5 != 3");
    /* GT: 5 > 3 → 1 */
    uint8_t c3[] = { PUSH_I, 5,0,0,0, PUSH_I, 3,0,0,0, GT, HALT };
    run_bytes(&vm, c3, sizeof(c3));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "5 > 3");
    /* LT: 3 < 5 → 1 */
    uint8_t c4[] = { PUSH_I, 3,0,0,0, PUSH_I, 5,0,0,0, LT, HALT };
    run_bytes(&vm, c4, sizeof(c4));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "3 < 5");
    /* NOT: NOT(1) → -1 */
    uint8_t c5[] = { PUSH_I, 1,0,0,0, NOT, HALT };
    run_bytes(&vm, c5, sizeof(c5));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), -1, "NOT(1)");
    /* NOT: NOT(0) → 1 */
    uint8_t c6[] = { PUSH_I, 0,0,0,0, NOT, HALT };
    run_bytes(&vm, c6, sizeof(c6));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "NOT(0)");
}

/* ── 7. 字节码: 变量 ── */
void test_vm_variables(void) {
    printf("  test_vm_variables...\n");
    VM vm;
    /* STORE 0 = 42, LOAD 0, HALT */
    uint8_t c1[] = { PUSH_I, 42,0,0,0, STORE, 0, LOAD, 0, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 42, "store/load var");
    /* Two vars: STORE 0 = 10, STORE 1 = 20, LOAD 0, LOAD 1, ADD, HALT */
    uint8_t c2[] = { PUSH_I, 10,0,0,0, STORE, 0, PUSH_I, 20,0,0,0, STORE, 1,
                     LOAD, 0, LOAD, 1, ADD, HALT };
    run_bytes(&vm, c2, sizeof(c2));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 30, "two vars add");
}

/* ── 8. 字节码: 控制流 ── */
void test_vm_control_flow(void) {
    printf("  test_vm_control_flow...\n");
    VM vm;
    /* JZ: PUSH_I 0, JZ → skip PUSH_I 99, push 1 */
    /* 0: PUSH_I 0, 2-5: JZ 8, 6-9: PUSH_I 99, 10-13: PUSH_I 1, 14: HALT */
    uint8_t c1[] = { PUSH_I, 0,0,0,0, JZ, 10,0,0,0,
                     PUSH_I, 99,0,0,0, PUSH_I, 1,0,0,0, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "JZ skips dead code");
    /* JNZ: PUSH_I 1, JNZ → jump to push 77 */
    /* 0: PUSH_I 1, 2-5: JNZ 10, 6-9: PUSH_I 0, 10-13: PUSH_I 77, 14: HALT */
    uint8_t c2[] = { PUSH_I, 1,0,0,0, JNZ, 10,0,0,0,
                     PUSH_I, 0,0,0,0, PUSH_I, 77,0,0,0, HALT };
    run_bytes(&vm, c2, sizeof(c2));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 77, "JNZ jumps");
    /* JMP: unconditional jump */
    uint8_t c3[] = { JMP, 8,0,0,0, PUSH_I, 99,0,0,0, PUSH_I, 55,0,0,0, HALT };
    run_bytes(&vm, c3, sizeof(c3));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 55, "JMP skips");
}

/* ── 9. 字节码: 字符串 ── */
void test_vm_strings(void) {
    printf("  test_vm_strings...\n");
    VM vm;
    /* PUSH_STR "hi" (len=2), STRLEN, HALT */
    uint8_t c1[] = { PUSH_STR, 2,0, 'h','i', STRLEN, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 2, "strlen 'hi'");
    /* PUSH_STR "a", PUSH_STR "b", CONCAT, HALT */
    uint8_t c2[] = { PUSH_STR, 1,0, 'a', PUSH_STR, 1,0, 'b', CONCAT, HALT };
    run_bytes(&vm, c2, sizeof(c2));
    void *top = vm.stack[vm.sp - 1];
    ASSERT(is_str(top), "concat result is string");
    ASSERT_EQ_STR(rt_str_c(top), "ab", "concat 'a'+'b'");
    /* STREQ */
    uint8_t c3[] = { PUSH_STR, 3,0, 'f','o','o', PUSH_STR, 3,0, 'f','o','o', STREQ, HALT };
    run_bytes(&vm, c3, sizeof(c3));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 1, "streq 'foo'=='foo'");
}

/* ── 10. 字节码: 列表 ── */
void test_vm_lists(void) {
    printf("  test_vm_lists...\n");
    VM vm;
    /* LIST_NEW 3: push 1,2,3 then LIST_NEW 3 → list [1,2,3] */
    uint8_t c1[] = { PUSH_I, 1,0,0,0, PUSH_I, 2,0,0,0, PUSH_I, 3,0,0,0,
                     LIST_NEW, 3, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    void *top = vm.stack[vm.sp - 1];
    ASSERT(is_list(top), "list_new creates list");
    rt_list_t *l = (rt_list_t*)top;
    ASSERT_EQ_INT(l->len, 3, "list len 3");
    ASSERT_EQ_INT(to_int(l->items[0]), 1, "list[0]=1");
    ASSERT_EQ_INT(to_int(l->items[1]), 2, "list[1]=2");
    ASSERT_EQ_INT(to_int(l->items[2]), 3, "list[2]=3");
    /* GET: list[1] */
    uint8_t c2[] = { PUSH_I, 10,0,0,0, PUSH_I, 20,0,0,0,
                     LIST_NEW, 2, PUSH_I, 0,0,0,0, GET, HALT };
    run_bytes(&vm, c2, sizeof(c2));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 10, "list[0]=10");
    /* LIST_LEN */
    uint8_t c3[] = { PUSH_I, 1,0,0,0, PUSH_I, 2,0,0,0, PUSH_I, 3,0,0,0, PUSH_I, 4,0,0,0,
                     LIST_NEW, 4, LIST_LEN, HALT };
    run_bytes(&vm, c3, sizeof(c3));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 4, "list_len 4");
}

/* ── 11. 字节码: 字典 ── */
void test_vm_dicts(void) {
    printf("  test_vm_dicts...\n");
    VM vm;
    /* DICT 1: push key=97('a'), value=100 → dict {"a": 100} */
    uint8_t c1[] = { PUSH_STR, 1,0, 'a', PUSH_I, 100,0,0,0,
                     DICT, 1, PUSH_STR, 1,0, 'a', DICT_GET, HALT };
    run_bytes(&vm, c1, sizeof(c1));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 100, "dict get 'a'");
    /* DICT_SET + DICT_GET: create dict, set key 1 = 99, get key 1 */
    /* DICT_SET pushes the value (not dict), so save dict in var0 first */
    uint8_t c4[] = {
        PUSH_I, 0,0,0,0, DICT, 0, STORE, 0,  /* var0 = dict() */
        LOAD, 0,                               /* push dict */
        PUSH_I, 1,0,0,0,                      /* push key=1 */
        PUSH_I, 99,0,0,0,                     /* push val=99 */
        DICT_SET,                              /* set, pushes val back */
        STORE, 1,                              /* var1 = 99 (discard) */
        LOAD, 0,                               /* push dict again */
        PUSH_I, 1,0,0,0,                      /* push key=1 */
        DICT_GET,                              /* get var0[key=1] */
        HALT
    };
    run_bytes(&vm, c4, sizeof(c4));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 99, "dict set/get int key");
}

/* ── 12. 字节码: 函数调用 ── */
void test_vm_function_call(void) {
    printf("  test_vm_function_call...\n");
    VM vm;
    /* C VM 约定: 调用前用 STORE 把参数写入目标函数的变量槽
     * 主代码:
     * 0: PUSH_I 5       — 参数值
     * 5: STORE 0        — 写入 var0（函数参数槽）
     * 7: CALL 0 → 12    — 0 个栈参数，跳转到 12
     * 12: LOAD 0, PUSH_I 2, MUL, RET  — 读 var0，乘 2，返回
     */
    uint8_t code[] = {
        PUSH_I, 5,0,0,0,       /* 0-4: push 5 */
        STORE, 0,              /* 5-6: var0 = 5 */
        CALL, 0,               /* 7-8: 0 stack args */
        14,0,0,0,              /* 9-12: target = 14 (function body) */
        HALT,                  /* 13 */
        /* function body at offset 14 */
        LOAD, 0,               /* 14-15: load var0 (param) */
        PUSH_I, 2,0,0,0,      /* 16-20: push 2 */
        MUL,                   /* 21: multiply */
        RET,                   /* 22: return */
    };
    run_bytes(&vm, code, sizeof(code));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 10, "func(5) * 2 = 10");
}

/* ── 13. 字节码: 嵌套调用 ── */
void test_vm_nested_call(void) {
    printf("  test_vm_nested_call...\n");
    VM vm;
    /* B at offset 30: LOAD 0, PUSH_I 1, ADD, RET  (x+1)
     * A at offset 20: STORE 0 (param), CALL → B, RET
     * main at offset 0: PUSH_I 10, STORE 0, CALL → A, HALT
     */
    uint8_t code[] = {
        /* main: store 10 to var0, call A */
        PUSH_I, 10,0,0,0,      /* 0-4: push 10 */
        STORE, 0,              /* 5-6: var0 = 10 */
        CALL, 0,               /* 7-8: 0 stack args */
        20,0,0,0,              /* 9-12: target A = 20 */
        HALT,                  /* 13 */
        0,0,0,0,0,0,           /* 14-19: padding */
        /* A at offset 20: read param, call B */
        LOAD, 0,               /* 20-21: load var0 (10) */
        STORE, 0,              /* 22-23: var0 = 10 (pass to B) */
        CALL, 0,               /* 24-25: 0 stack args */
        34,0,0,0,              /* 26-29: target B = 34 */
        RET,                   /* 30 */
        0,0,0,                 /* 31-33: padding */
        /* B at offset 34: return x + 1 */
        LOAD, 0,               /* 34-35: load var0 */
        PUSH_I, 1,0,0,0,      /* 36-40: push 1 */
        ADD,                   /* 41: add */
        RET,                   /* 42: return */
    };
    run_bytes(&vm, code, sizeof(code));
    ASSERT_EQ_INT(to_int(vm.stack[vm.sp - 1]), 11, "nested: A calls B(10) → 11");
}

/* ═══════════════════════════════════════════════════
 * 主函数
 * ═══════════════════════════════════════════════════ */
int main(void) {
    vm_register_device(0, mock_read, NULL);
    vm_register_device(1, NULL, mock_write);

    printf("=== C VM 单元测试 ===\n");
    test_tagged_integers();
    test_strings();
    test_lists();
    test_dicts();
    test_vm_arithmetic();
    test_vm_comparison();
    test_vm_variables();
    test_vm_control_flow();
    test_vm_strings();
    test_vm_lists();
    test_vm_dicts();
    test_vm_function_call();
    test_vm_nested_call();

    printf("\n%d tests, %d passed, %d failed\n", _tests_run, _tests_passed, _tests_failed);
    return _tests_failed > 0 ? 1 : 0;
}
