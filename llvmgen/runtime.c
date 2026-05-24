/* 三言 LLVM 编译运行时库 (libsanyan_rt)
 *
 * 所有字符串函数接受 void*（LLVM 直接传入的全局字符串指针 或 rt_str_t*）。
 * 内部通过 _cstr() 统一提取 C 字符串。
 *
 * 编译:  gcc -c runtime.c -o runtime.o -std=c99
 * 链接:  gcc main.o runtime.o -o a.out
 */

#ifdef _WIN32
void __chkstk(void) {}
#include <windows.h>
#else
#include <unistd.h>
#endif

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>

/* ── 字符串 Arena 分配器 ──
 *
 * 替代逐次 malloc：所有字符串操作从 arena 分配，搬指针而非调 malloc。
 * auto-grow：容量不足时双倍扩容（不 free 旧块，等程序结束一次性回收）。
 */
typedef struct {
    char *base;
    size_t used;
    size_t cap;
} san_arena_t;

static san_arena_t g_arena;

void rt_arena_init(size_t cap) {
    if (cap < 65536) cap = 65536;
    g_arena.base = (char*)malloc(cap);
    g_arena.used = 0;
    g_arena.cap = cap;
}

static void *_arena_alloc(san_arena_t *a, size_t size) {
    size_t aligned = (size + 7) & ~(size_t)7;
    if (a->used + aligned > a->cap) {
        size_t new_cap = a->cap * 2;
        if (new_cap < a->used + aligned) new_cap = (a->used + aligned) * 2;
        char *nb = (char*)malloc(new_cap);
        if (nb && a->base) memcpy(nb, a->base, a->used);
        a->base = nb;
        a->cap = new_cap;
    }
    void *ptr = a->base + a->used;
    a->used += aligned;
    return ptr;
}

/* ── 堆对象类型标签 ── */
typedef enum {
    OBJ_STRING = 1,
    OBJ_LIST   = 2,
    OBJ_DICT   = 3,
    OBJ_FLOAT  = 4,
} san_obj_type_t;

#define SAN_HEADER uint32_t h_type

/* ── 内部字符串类型 ── */
typedef struct {
    SAN_HEADER;
    int32_t len;
    char data[];
} rt_str_t;

static rt_str_t *_rt_make(const char *s) {
    if (!s) return NULL;
    if (!g_arena.base) rt_arena_init(65536);
    int32_t len = (int32_t)strlen(s);
    size_t total = sizeof(rt_str_t) + (size_t)len + 1;
    rt_str_t *st = (rt_str_t *)_arena_alloc(&g_arena, total);
    if (!st) return NULL;
    st->h_type = OBJ_STRING;
    st->len = len;
    memcpy(st->data, s, (size_t)len + 1);
    return st;
}

/* ── 统一字符串访问 ──
 *
 * 所有运行时字符串以 rt_str_t（i32 len + data[]）格式传递。
 * 全局字符串常量通过 _make_rt_string() 生成，也是 rt_str_t 格式。
 * _cstr() 直接返回 data 字段，无需启发式检测。
 */
static const char *_cstr(const void *p) {
    if (!p) return NULL;
    return ((rt_str_t *)p)->data;
}

static int32_t _cstr_len(const void *p) {
    if (!p) return 0;
    return ((rt_str_t *)p)->len;
}

/* ── 字符串 API（全部接受 void*）── */

void *rt_str_concat(const void *a, const void *b) {
    if (!a && !b) return NULL;
    if (!a) return _rt_make(_cstr(b));
    if (!b) return _rt_make(_cstr(a));
    const char *ca = _cstr(a), *cb = _cstr(b);
    int32_t la = (int32_t)strlen(ca), lb = (int32_t)strlen(cb);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + la + lb + 1);
    if (!st) return NULL;
    st->len = la + lb;
    memcpy(st->data, ca, la);
    memcpy(st->data + la, cb, lb + 1);
    return st;
}

int32_t rt_str_len(const void *s)   { return _cstr_len(s); }

void *rt_str_substr(const void *s, int32_t start, int32_t len) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s);
    if (start < 0 || len <= 0) return _rt_make("");
    int32_t slen = _cstr_len(s);
    if (start >= slen) return _rt_make("");
    if (start + len > slen) len = slen - start;
    char *buf = (char *)malloc((size_t)len + 1);
    memcpy(buf, cs + start, (size_t)len);
    buf[len] = '\0';
    rt_str_t *r = _rt_make(buf);
    free(buf);
    return r;
}

int32_t rt_str_equals(const void *a, const void *b) {
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    return strcmp(_cstr(a), _cstr(b)) == 0 ? 1 : 0;
}

int32_t rt_str_contains(const void *hs, const void *ndl) {
    if (!hs || !ndl) return 0;
    return strstr(_cstr(hs), _cstr(ndl)) ? 1 : 0;
}

int32_t rt_str_find(const void *hs, const void *ndl) {
    if (!hs || !ndl) return -1;
    const char *chs = _cstr(hs), *cndl = _cstr(ndl);
    char *p = strstr(chs, cndl);
    return p ? (int32_t)(p - chs) : -1;
}

void *rt_int_to_str(uintptr_t tagged) {
    int64_t val = (int64_t)((intptr_t)tagged >> 1);
    char buf[32];
    snprintf(buf, sizeof(buf), "%lld", (long long)val);
    return _rt_make(buf);
}

/* ── 前置声明 ── */
typedef struct rt_list_s rt_list_t;
rt_list_t *rt_list_new(void);
void rt_list_push_item(void *lstp, void *item);

void *rt_str_split(const char *s, const char *sep) {
    rt_list_t *r = rt_list_new();
    if (!s || !sep || !r) return r;
    const char *cs = _cstr(s), *csep = _cstr(sep);
    if (!cs || !csep || !*cs) return r;
    int32_t slen = (int32_t)strlen(cs), seplen = (int32_t)strlen(csep);
    if (seplen <= 0) { rt_list_push_item(r, _rt_make(cs));     return r;
}

/* ── 桩函数（待完整实现）────────────────── */
void *rt_http_get(void *url)         { (void)url; return _rt_make(\"\"); }
void *rt_http_post(void *url, void *d){ (void)url; (void)d; return _rt_make(\"\"); }
void *rt_regex_match(void *p, void *t){ (void)p; (void)t; return _rt_make(\"\"); }
void *rt_regex_search(void *p, void *t){ (void)p; (void)t; return _rt_make(\"\"); }
void *rt_regex_findall(void *p, void *t){ (void)p; (void)t; return _rt_make(\"\"); }
void *rt_regex_replace(void *p, void *r, void *t){ (void)p; (void)r; (void)t; return _rt_make(\"\"); }
void *rt_regex_split(void *p, void *t){ (void)p; (void)t; return _rt_make(\"\"); }
void *rt_str_reverse(void *s)        { return _rt_make(_cstr(s)); }
int32_t rt_str_startswith(void *s, void *pre) { return strncmp(_cstr(s), _cstr(pre), strlen(_cstr(pre))) == 0; }
int32_t rt_str_endswith(void *s, void *suf)   { const char *cs=_cstr(s),*csu=_cstr(suf); int32_t l=(int32_t)strlen(cs),ls=(int32_t)strlen(csu); return l>=ls && strcmp(cs+l-ls,csu)==0; }
void *rt_str_replace(void *s, void *o, void *n){ (void)s;(void)o;(void)n; return _rt_make(\"\"); }
void *rt_str_trim(void *s)            { return _rt_make(_cstr(s)); }
void *rt_str_upper(void *s)           { return _rt_make(_cstr(s)); }
void *rt_str_lower(void *s)           { return _rt_make(_cstr(s)); }
void *rt_str_join(void *sep, void *lst){ (void)sep;(void)lst; return _rt_make(\"\"); }
void *rt_list_sort(void *lst)         { (void)lst; return _rt_make(\"\"); }
int32_t rt_list_sum(void *lst)        { (void)lst; return 0; }
int32_t rt_list_count(void *lst, void *v){ (void)lst;(void)v; return 0; }
void *rt_list_unique(void *lst)       { (void)lst; return _rt_make(\"\"); }
    const char *p = cs;
    while (p && *p) {
        const char *next = strstr(p, csep);
        if (!next) { rt_list_push_item(r, _rt_make(p)); break; }
        int32_t part_len = (int32_t)(next - p);
        char *buf = (char *)malloc((size_t)part_len + 1);
        if (buf) { memcpy(buf, p, (size_t)part_len); buf[part_len] = '\0'; }
        rt_list_push_item(r, _rt_make(buf ? buf : ""));
        free(buf);
        p = next + seplen;
    }
    return r;
}

/* ── JSON 桩（完整实现待加）── */
void *rt_json_parse(void *s) {
    (void)s;
    return _rt_make("{}");
}

void *rt_json_stringify(void *v) {
    (void)v;
    return _rt_make("\"\"");
}

/* ── 浮点类型 ── */
typedef struct {
    SAN_HEADER;
    double value;
} rt_float_t;

static san_arena_t g_float_arena;

void *rt_float_new(double v) {
    if (!g_float_arena.base) rt_arena_init(65536);
    rt_float_t *f = (rt_float_t *)_arena_alloc(&g_float_arena, sizeof(rt_float_t));
    if (!f) return NULL;
    f->h_type = OBJ_FLOAT;
    f->value = v;
    return f;
}

double rt_unbox_float(void *v) {
    if (!v) return 0.0;
    return ((rt_float_t *)v)->value;
}

void *rt_int_to_float(uintptr_t tagged) {
    int64_t val = (int64_t)((intptr_t)tagged >> 1);
    return rt_float_new((double)val);
}

/* ── 列表类型 ── */
struct rt_list_s {
    SAN_HEADER;
    int32_t len;
    int32_t cap;
    void **items;
};
/* rt_list_t 已在文件顶部通过 typedef 声明 */

rt_list_t *rt_list_new(void) {
    rt_list_t *lst = (rt_list_t *)calloc(1, sizeof(rt_list_t));
    if (!lst) return NULL;
    lst->h_type = OBJ_LIST;
    lst->cap = 4;
    lst->items = (void **)calloc(4, sizeof(void *));
    return lst;
}

rt_list_t *rt_list_new_cap(int32_t cap) {
    rt_list_t *lst = (rt_list_t *)calloc(1, sizeof(rt_list_t));
    if (!lst) return NULL;
    if (cap < 4) cap = 4;
    lst->h_type = OBJ_LIST;
    lst->cap = cap;
    lst->items = (void **)calloc((size_t)cap, sizeof(void *));
    return lst;
}

void rt_list_push_item(void *lstp, void *item) {
    rt_list_t *lst = (rt_list_t *)lstp;
    if (!lst) return;
    if (lst->len >= lst->cap) { lst->cap *= 2; lst->items = realloc(lst->items, (size_t)lst->cap * sizeof(void *)); }
    lst->items[lst->len++] = item;
}

int32_t rt_list_len(rt_list_t *lst) { return lst ? lst->len : 0; }

void *rt_list_get(rt_list_t *lst, int32_t idx) {
    if (!lst || idx < 0 || idx >= lst->len) return NULL;
    return lst->items[idx];
}

rt_list_t *rt_list_concat(rt_list_t *a, rt_list_t *b) {
    rt_list_t *r = rt_list_new();
    if (!r) return NULL;
    if (a) for (int32_t i = 0; i < a->len; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, (size_t)r->cap * sizeof(void *)); }
        r->items[r->len++] = a->items[i];
    }
    if (b) for (int32_t i = 0; i < b->len; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, (size_t)r->cap * sizeof(void *)); }
        r->items[r->len++] = b->items[i];
    }
    return r;
}

/* ── 字典类型（开放寻址哈希表）── */
#define RT_DICT_INIT_CAP 16
#define RT_DICT_LOAD_FACTOR 70  /* 百分比 */

typedef struct {
    char *key;
    void *value;
    int used;   /* 0=empty, 1=occupied */
} rt_entry_t;

typedef struct {
    SAN_HEADER;
    int32_t count;
    int32_t cap;
    rt_entry_t *entries;
} rt_dict_t;

/* FNV-1a hash */
static uint32_t _hash_str(const char *s) {
    uint32_t h = 2166136261u;
    for (; *s; s++) {
        h ^= (uint8_t)*s;
        h *= 16777619u;
    }
    return h;
}

static void _dict_resize(rt_dict_t *d, int32_t new_cap) {
    rt_entry_t *old = d->entries;
    int32_t old_cap = d->cap;
    d->entries = (rt_entry_t*)calloc((size_t)new_cap, sizeof(rt_entry_t));
    d->cap = new_cap;
    d->count = 0;
    for (int32_t i = 0; i < old_cap; i++) {
        if (old[i].used) {
            uint32_t h = _hash_str(old[i].key);
            for (int32_t j = 0; j < new_cap; j++) {
                int32_t idx = (int32_t)((h + (uint32_t)j) % (uint32_t)new_cap);
                if (!d->entries[idx].used) {
                    d->entries[idx] = old[i];
                    d->count++;
                    break;
                }
            }
        }
    }
    free(old);
}

void *rt_dict_new(void) {
    rt_dict_t *d = (rt_dict_t*)calloc(1, sizeof(rt_dict_t));
    if (!d) return NULL;
    d->h_type = OBJ_DICT;
    d->cap = RT_DICT_INIT_CAP;
    d->entries = (rt_entry_t*)calloc(RT_DICT_INIT_CAP, sizeof(rt_entry_t));
    return d;
}

static char *_strdup_key(const void *kp) {
    const char *s = _cstr(kp);
    if (!s) return NULL;
    size_t len = strlen(s);
    char *d = (char *)malloc(len + 1);
    if (d) memcpy(d, s, len + 1);
    return d;
}

static int32_t _dict_find(rt_dict_t *d, const char *key) {
    if (!d || d->count == 0) return -1;
    uint32_t h = _hash_str(key);
    for (int32_t j = 0; j < d->cap; j++) {
        int32_t idx = (int32_t)((h + (uint32_t)j) % (uint32_t)d->cap);
        if (!d->entries[idx].used) return -1;
        if (d->entries[idx].key && strcmp(d->entries[idx].key, key) == 0)
            return idx;
    }
    return -1;
}

static void _dict_grow(rt_dict_t *d) {
    int32_t new_cap = d->cap * 2;
    if (new_cap < RT_DICT_INIT_CAP) new_cap = RT_DICT_INIT_CAP;
    _dict_resize(d, new_cap);
}

int32_t rt_dict_contains(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return 0;
    return _dict_find(d, _cstr(kp)) >= 0 ? 1 : 0;
}

void *rt_dict_get(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return NULL;
    int32_t idx = _dict_find(d, _cstr(kp));
    return idx >= 0 ? d->entries[idx].value : NULL;
}

void rt_dict_set(void *dp, void *kp, void *vp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return;
    const char *key = _cstr(kp);
    int32_t idx = _dict_find(d, key);
    if (idx >= 0) {
        d->entries[idx].value = vp;
        return;
    }
    if (d->count * 100 >= d->cap * RT_DICT_LOAD_FACTOR)
        _dict_grow(d);
    uint32_t h = _hash_str(key);
    for (int32_t j = 0; j < d->cap; j++) {
        idx = (int32_t)((h + (uint32_t)j) % (uint32_t)d->cap);
        if (!d->entries[idx].used) {
            d->entries[idx].key = _strdup_key(kp);
            d->entries[idx].value = vp;
            d->entries[idx].used = 1;
            d->count++;
            return;
        }
    }
}

/* rt_dict_from_pairs: 从键值对列表填充字典 */
void *rt_dict_from_pairs(void *dictp, void *pairs_list) {
    rt_dict_t *d = (rt_dict_t *)dictp;
    rt_list_t *pairs = (rt_list_t *)pairs_list;
    if (!d || !pairs) return dictp;
    for (int32_t i = 0; i + 1 < pairs->len; i += 2) {
        rt_dict_set(d, pairs->items[i], pairs->items[i + 1]);
    }
    return dictp;
}

/* ── 随机数 ── */
static int _rand_ok = 0;
int32_t rt_random_int(int32_t lo, int32_t hi) {
    if (!_rand_ok) { srand((unsigned)time(NULL)); _rand_ok = 1; }
    if (lo > hi) { int32_t t = lo; lo = hi; hi = t; }
    return lo + rand() % (hi - lo + 1);
}
int32_t rt_random_trit(void) {
    if (!_rand_ok) { srand((unsigned)time(NULL)); _rand_ok = 1; }
    int r = rand() % 3;
    return r == 0 ? -1 : (r == 1 ? 0 : 1);
}

/* ── 输出 ── */
void rt_print_str(const void *p) {
    if (!p) return;
    printf("%s\n", _cstr(p));
}

void rt_print_float(void *v) {
    if (!v) return;
    printf("%.15g\n", ((rt_float_t *)v)->value);
}

/* ── 等待（参数为秒）── */
void rt_sleep(int32_t sec) {
    int32_t ms = sec * 1000;
#ifdef _WIN32
    Sleep((DWORD)ms);
#else
    usleep((useconds_t)ms * 1000);
#endif
}

/* ── 文件操作 ── */
void *rt_read_file(const char *path) {
    if (!path) return _rt_make("");
    const char *rp = _cstr(path);
    if (!rp) return _rt_make("");
    FILE *f = fopen(rp, "rb");
    if (!f) return _rt_make("");
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    if (buf) { fread(buf, 1, (size_t)sz, f); buf[sz] = '\0'; }
    fclose(f);
    rt_str_t *r = _rt_make(buf ? buf : "");
    free(buf);
    return r;
}

void rt_write_file(const char *path, const char *content) {
    if (!path || !content) return;
    const char *rp = _cstr(path), *rc = _cstr(content);
    FILE *f = fopen(rp, "w");
    if (!f) return;
    fwrite(rc, 1, strlen(rc), f);
    fclose(f);
}

/* ── 输入 ── */
void *rt_read_input(void) {
    char buf[4096] = {0};
    if (fgets(buf, sizeof(buf), stdin)) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
        return _rt_make(buf);
    }
    return _rt_make("");
}

/* ── IoT 设备注册表 ── */
#define RT_IOT_MAX 16
typedef struct { char name[32]; int32_t state; } rt_iot_dev_t;
static rt_iot_dev_t _iot_devs[RT_IOT_MAX];
static int32_t _iot_count = 0;

static rt_iot_dev_t *_iot_find(const char *name) {
    const char *rn = _cstr(name);
    if (!rn) return NULL;
    for (int32_t i = 0; i < _iot_count; i++)
        if (strcmp(_iot_devs[i].name, rn) == 0) return &_iot_devs[i];
    if (_iot_count < RT_IOT_MAX) {
        rt_iot_dev_t *d = &_iot_devs[_iot_count++];
        strncpy(d->name, rn, 31); d->name[31] = '\0'; d->state = 0;
        return d;
    }
    return NULL;
}

void rt_iot_set(void *dp, void *sp) {
    const char *name = _cstr(dp);
    const char *state = _cstr(sp);
    if (!name) return;
    rt_iot_dev_t *d = _iot_find(name);
    if (!d || !state) return;
    if (strcmp(state, "开") == 0 || strcmp(state, "亮") == 0) d->state = 1;
    else if (strcmp(state, "关") == 0 || strcmp(state, "灭") == 0) d->state = -1;
    else if (strcmp(state, "守") == 0) d->state = 0;
}

void *rt_iot_read(void *dp) {
    const char *name = _cstr(dp);
    if (!name) return _rt_make("0");
    rt_iot_dev_t *d = _iot_find(name);
    if (!d) return _rt_make("0");
    char buf[2] = {0};
    snprintf(buf, sizeof(buf), "%d", d->state);
    return _rt_make(buf);
}

void rt_iot_query(void *dp) {
    const char *name = _cstr(dp);
    if (!name) return;
    rt_iot_dev_t *d = _iot_find(name);
    if (d) printf("[IoT] %s = %s\n", d->name, d->state == 1 ? "开" : (d->state == -1 ? "关" : "守"));
}

void rt_iot_with(void *dp, void *bp) { (void)dp; (void)bp; }

/* ── 类型判断 ── */
int32_t rt_is_number(int32_t v) { (void)v; return 1; }

int32_t rt_is_string(void *p) {
    if (!p) return 0;
    if ((uintptr_t)p & 1) return 0;  /* tagged int */
    return 1;
}

int32_t rt_is_list(void *p) {
    if (!p) return 0;
    if ((uintptr_t)p & 1) return 0;  /* tagged int */
    return 1;
}

/* ── 异常处理（LLVM IR 可见全局）──
 *
 * LLVM codegen 直接 load/store @g_error，不再调用 opaque 函数。
 * rt_throw 仅设置标记，try/catch 的检查由 LLVM IR 内联完成。
 */
void *g_error = NULL;                   /* LLVM 可见：@g_error = global i8* null */

void rt_throw(void *msg) {
    g_error = msg;
}

/* ── 桩 ── */
void *rt_import(void *path)              { (void)path; return _rt_make(""); }

/* ── 内存管理 ── */
void rt_free_str(rt_str_t *s) { if (s) free(s); }

/* ── 列表切片 ── */
void *rt_list_slice(void *lstp, int32_t start, int32_t end) {
    rt_list_t *lst = (rt_list_t *)lstp;
    rt_list_t *r = rt_list_new();
    if (!lst || !r) return r;
    if (start < 0) start = 0;
    if (end > lst->len) end = lst->len;
    for (int32_t i = start; i < end; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, (size_t)r->cap * sizeof(void *)); }
        r->items[r->len++] = lst->items[i];
    }
    return r;
}

/* ── 字符串转字符列表 ── */
void *rt_str_to_list(const char *s) {
    rt_list_t *r = rt_list_new();
    const char *cs = _cstr(s);
    if (!cs || !r) return r;
    for (int32_t i = 0; cs[i]; i++) {
        char buf[2] = {cs[i], 0};
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, (size_t)r->cap * sizeof(void *)); }
        r->items[r->len++] = _rt_make(buf);
    }
    return r;
}
