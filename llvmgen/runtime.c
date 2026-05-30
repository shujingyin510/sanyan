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

/* ═══════════════════════════════════════════════════════════
 * Arena 分配器
 * 所有字符串从 arena 分配，auto-grow，程序结束一次性回收。
 * ═══════════════════════════════════════════════════════════ */
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
    size_t aligned = (size + 7) & ~(size_t)7;  /* 8 字节对齐 */
    if (a->used + aligned > a->cap) {
        /* 容量不足时双倍扩容 */
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

/* ═══════════════════════════════════════════════════════════
 * 堆对象头部
 * 所有堆对象（字符串/列表/字典/浮点）共用 h_type 标签。
 * ═══════════════════════════════════════════════════════════ */
typedef enum {
    OBJ_STRING = 1,
    OBJ_LIST   = 2,
    OBJ_DICT   = 3,
    OBJ_FLOAT  = 4,
} san_obj_type_t;

#define SAN_HEADER uint32_t h_type

/* ═══════════════════════════════════════════════════════════
 * 字符串类型 (rt_str_t)
 * 格式: [h_type][len][data...]，flexible array member。
 * ═══════════════════════════════════════════════════════════ */
typedef struct {
    SAN_HEADER;
    int32_t len;
    char data[];
} rt_str_t;

/* 从 C 字符串创建 rt_str_t（arena 分配） */
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

/* 公共接口：从 C 字符串创建三言字符串 */
void *rt_make(const char *s) {
    return _rt_make(s);
}

/* ═══════════════════════════════════════════════════════════
 * 统一字符串访问
 * 所有运行时字符串以 rt_str_t 格式传递。
 * _cstr() 提取 data 字段，_cstr_len() 提取长度。
 * ═══════════════════════════════════════════════════════════ */
static const char *_cstr(const void *p) {
    if (!p) return NULL;
    return ((rt_str_t *)p)->data;
}

static int32_t _cstr_len(const void *p) {
    if (!p) return 0;
    return ((rt_str_t *)p)->len;
}

/* ═══════════════════════════════════════════════════════════
 * 字符串操作
 * ═══════════════════════════════════════════════════════════ */

/* 连接两个字符串 */
void *rt_str_concat(const void *a, const void *b) {
    if (!a && !b) return NULL;
    if (!a) return _rt_make(_cstr(b));
    if (!b) return _rt_make(_cstr(a));
    const char *ca = _cstr(a), *cb = _cstr(b);
    int32_t la = (int32_t)strlen(ca), lb = (int32_t)strlen(cb);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + la + lb + 1);
    if (!st) return NULL;
    st->h_type = OBJ_STRING;
    st->len = la + lb;
    memcpy(st->data, ca, la);
    memcpy(st->data + la, cb, lb + 1);
    return st;
}

/* 字符串长度（字符数） */
int32_t rt_str_len(const void *s) { return _cstr_len(s); }

/* 子串提取 [start, start+len) */
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

/* 字符串相等比较 */
int32_t rt_str_equals(const void *a, const void *b) {
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    return strcmp(_cstr(a), _cstr(b)) == 0 ? 1 : 0;
}

/* 字符串包含检查 */
int32_t rt_str_contains(const void *hs, const void *ndl) {
    if (!hs || !ndl) return 0;
    return strstr(_cstr(hs), _cstr(ndl)) ? 1 : 0;
}

/* 字符串查找，返回索引或 -1 */
int32_t rt_str_find(const void *hs, const void *ndl) {
    if (!hs || !ndl) return -1;
    const char *chs = _cstr(hs), *cndl = _cstr(ndl);
    char *p = strstr(chs, cndl);
    return p ? (int32_t)(p - chs) : -1;
}

/* 整数转字符串 */
void *rt_int_to_str(uintptr_t tagged) {
    int64_t val = (int64_t)((intptr_t)tagged >> 1);
    char buf[32];
    snprintf(buf, sizeof(buf), "%lld", (long long)val);
    return _rt_make(buf);
}

/* 前置声明 */
typedef struct rt_list_s rt_list_t;

/* 列表类型 — 必须在使用其成员的函数之前定义 */
struct rt_list_s {
    SAN_HEADER;
    int32_t len;
    int32_t cap;
    void **items;
};

rt_list_t *rt_list_new(void);
void rt_list_push_item(void *lstp, void *item);

/* 字符串按分隔符分割为列表 */
void *rt_str_split(void *s, void *sep) {
    rt_list_t *r = rt_list_new();
    if (!s || !sep || !r) return r;
    const char *cs = _cstr(s), *csep = _cstr(sep);
    if (!cs || !csep || !*cs) return r;
    int32_t seplen = (int32_t)strlen(csep);
    if (seplen <= 0) { rt_list_push_item(r, _rt_make(cs)); return r; }
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

/* 字符串反转 */
void *rt_str_reverse(void *s) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s);
    int32_t len = (int32_t)strlen(cs);
    char *buf = (char*)malloc(len + 1);
    for (int32_t i = 0; i < len; i++) buf[i] = cs[len - 1 - i];
    buf[len] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* 前缀检查 */
int32_t rt_str_startswith(void *s, void *pre) {
    if (!s || !pre) return 0;
    const char *cs = _cstr(s), *cp = _cstr(pre);
    if (!cs || !cp) return 0;
    return strncmp(cs, cp, strlen(cp)) == 0;
}

/* 后缀检查 */
int32_t rt_str_endswith(void *s, void *suf) {
    if (!s || !suf) return 0;
    const char *cs = _cstr(s), *csu = _cstr(suf);
    if (!cs || !csu) return 0;
    int32_t l = (int32_t)strlen(cs), lu = (int32_t)strlen(csu);
    return l >= lu && strncmp(cs + l - lu, csu, lu) == 0;
}

/* 字符串替换 */
void *rt_str_replace(void *s, void *o, void *n) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s), *co = _cstr(o), *cn = _cstr(n);
    if (!cs) return _rt_make("");
    if (!co || !*co) return _rt_make(cs);  /* 空模式 → 原串 */
    int32_t sl = (int32_t)strlen(cs), ol = (int32_t)strlen(co);
    int32_t nl = cn ? (int32_t)strlen(cn) : 0;
    /* 最坏情况：每字符都匹配 */
    int32_t max_len = (ol > 0 ? (sl / ol) * nl : 0) + sl + 1;
    char *buf = (char*)malloc((size_t)max_len);
    int32_t bi = 0, si = 0;
    while (si < sl) {
        if (si + ol <= sl && strncmp(cs + si, co, ol) == 0) {
            if (cn) { memcpy(buf + bi, cn, nl); bi += nl; }
            si += ol;
        } else {
            buf[bi++] = cs[si++];
        }
    }
    buf[bi] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* 去除首尾空白 */
void *rt_str_trim(void *s) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s);
    if (!cs) return _rt_make("");
    while (*cs == ' ' || *cs == '\t' || *cs == '\n' || *cs == '\r') cs++;
    int32_t len = (int32_t)strlen(cs);
    while (len > 0 && (cs[len-1] == ' ' || cs[len-1] == '\t' || cs[len-1] == '\n' || cs[len-1] == '\r')) len--;
    char *buf = (char*)malloc(len + 1);
    memcpy(buf, cs, len); buf[len] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* 转大写（仅 ASCII） */
void *rt_str_upper(void *s) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s);
    if (!cs) return _rt_make("");
    int32_t len = (int32_t)strlen(cs);
    char *buf = (char*)malloc(len + 1);
    for (int32_t i = 0; i < len; i++)
        buf[i] = (cs[i] >= 'a' && cs[i] <= 'z') ? cs[i] - 32 : cs[i];
    buf[len] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* 转小写（仅 ASCII） */
void *rt_str_lower(void *s) {
    if (!s) return _rt_make("");
    const char *cs = _cstr(s);
    if (!cs) return _rt_make("");
    int32_t len = (int32_t)strlen(cs);
    char *buf = (char*)malloc(len + 1);
    for (int32_t i = 0; i < len; i++)
        buf[i] = (cs[i] >= 'A' && cs[i] <= 'Z') ? cs[i] + 32 : cs[i];
    buf[len] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* 列表按分隔符拼接为字符串 */
void *rt_str_join(void *sep, void *lst) {
    const char *csep = sep ? _cstr(sep) : "";
    if (!csep) csep = "";
    rt_list_t *l = (rt_list_t*)lst;
    if (!l || l->len == 0) return _rt_make("");
    int32_t sep_len = (int32_t)strlen(csep);
    /* 计算总长度 */
    int32_t total = 0;
    for (int32_t i = 0; i < l->len; i++) {
        const char *item = _cstr(l->items[i]);
        total += (int32_t)(item ? strlen(item) : 0);
        if (i > 0) total += sep_len;
    }
    char *buf = (char*)malloc((size_t)total + 1);
    int32_t pos = 0;
    for (int32_t i = 0; i < l->len; i++) {
        if (i > 0) { memcpy(buf + pos, csep, sep_len); pos += sep_len; }
        const char *item = _cstr(l->items[i]);
        if (item) { int32_t il = (int32_t)strlen(item); memcpy(buf + pos, item, il); pos += il; }
    }
    buf[pos] = '\0';
    void *result = _rt_make(buf);
    free(buf);
    return result;
}

/* ═══════════════════════════════════════════════════════════
 * HTTP / 正则（桩函数，待完整实现）
 * ═══════════════════════════════════════════════════════════ */
void *rt_http_get(void *url)                    { (void)url; return _rt_make(""); }
void *rt_http_post(void *url, void *d)          { (void)url; (void)d; return _rt_make(""); }
void *rt_regex_match(void *p, void *t)          { (void)p; (void)t; return _rt_make(""); }
void *rt_regex_search(void *p, void *t)         { (void)p; (void)t; return _rt_make(""); }
void *rt_regex_findall(void *p, void *t)        { (void)p; (void)t; return _rt_make(""); }
void *rt_regex_replace(void *p, void *r, void *t){ (void)p; (void)r; (void)t; return _rt_make(""); }
void *rt_regex_split(void *p, void *t)          { (void)p; (void)t; return _rt_make(""); }

/* ═══════════════════════════════════════════════════════════
 * 列表操作
 * ═══════════════════════════════════════════════════════════ */

/* 列表排序（插入排序，按 tagged int 值比较） */
void *rt_list_sort(void *lst) {
    rt_list_t *l = (rt_list_t*)lst;
    if (!l || l->len <= 1) return lst;
    rt_list_t *result = rt_list_new();
    for (int32_t i = 0; i < l->len; i++) rt_list_push_item(result, l->items[i]);
    for (int32_t i = 1; i < result->len; i++) {
        void *key = result->items[i];
        int32_t j = i - 1;
        while (j >= 0 && (intptr_t)result->items[j] > (intptr_t)key) {
            result->items[j + 1] = result->items[j];
            j--;
        }
        result->items[j + 1] = key;
    }
    return result;
}

/* 列表求和（tagged int 累加） */
int32_t rt_list_sum(void *lst) {
    rt_list_t *l = (rt_list_t*)lst;
    if (!l) return 0;
    int32_t sum = 0;
    for (int32_t i = 0; i < l->len; i++) sum += (int32_t)(intptr_t)l->items[i];
    return sum;
}

/* 列表元素计数 */
int32_t rt_list_count(void *lst, void *v) {
    rt_list_t *l = (rt_list_t*)lst;
    if (!l) return 0;
    int32_t count = 0;
    for (int32_t i = 0; i < l->len; i++) {
        if ((intptr_t)l->items[i] == (intptr_t)v) count++;
    }
    return count;
}

/* 列表去重 */
void *rt_list_unique(void *lst) {
    rt_list_t *l = (rt_list_t*)lst;
    if (!l) return lst;
    rt_list_t *result = rt_list_new();
    for (int32_t i = 0; i < l->len; i++) {
        int found = 0;
        for (int32_t j = 0; j < result->len; j++) {
            if ((intptr_t)result->items[j] == (intptr_t)l->items[i]) { found = 1; break; }
        }
        if (!found) rt_list_push_item(result, l->items[i]);
    }
    return result;
}

/* 列表元素设置 */
void rt_list_set(void *lst, int32_t i, void *v) {
    rt_list_t *l = (rt_list_t*)lst;
    if (l && i >= 0 && i < l->len) l->items[i] = v;
}

/* 列表归并（桩） */
void *rt_list_reduce(void *fn, void *lst) { (void)fn; (void)lst; return _rt_make(""); }

/* ═══════════════════════════════════════════════════════════
 * 数学函数
 * ═══════════════════════════════════════════════════════════ */

/* 幂运算（快速幂） */
int32_t rt_math_pow(int32_t b, int32_t e) {
    if (e < 0) return 0;
    int32_t r = 1;
    while (e > 0) {
        if (e & 1) r *= b;
        b *= b;
        e >>= 1;
    }
    return r;
}

/* 整数平方根（牛顿法，处理负数） */
int32_t rt_math_sqrt(int32_t v) {
    if (v <= 0) return 0;
    int32_t r = v;
    while (r > v / r) r = (r + v / r) / 2;
    return r;
}

/* 绝对值 */
int32_t rt_math_abs(int32_t v) { return v < 0 ? -v : v; }

/* 向下取整（整数恒等） */
int32_t rt_math_floor(int32_t v) { return v; }

/* 向上取整（整数恒等） */
int32_t rt_math_ceil(int32_t v) { return v; }

/* 四舍五入（整数恒等） */
int32_t rt_math_round(int32_t v) { return v; }

/* 不大于 (<=) */
int32_t rt_math_ngt(int32_t a, int32_t b) { return a <= b; }

/* 不小于 (>=) */
int32_t rt_math_nlt(int32_t a, int32_t b) { return a >= b; }

/* ═══════════════════════════════════════════════════════════
 * 时间
 * ═══════════════════════════════════════════════════════════ */

/* 当前 Unix 时间戳（秒） */
int32_t rt_time_now(void) { return (int32_t)time(NULL); }

/* ═══════════════════════════════════════════════════════════
 * JSON（桩函数，待完整实现）
 * ═══════════════════════════════════════════════════════════ */
void *rt_json_parse(void *s)     { (void)s; return _rt_make("{}"); }
void *rt_json_stringify(void *v) { (void)v; return _rt_make("\"\""); }

/* ═══════════════════════════════════════════════════════════
 * 浮点类型
 * ═══════════════════════════════════════════════════════════ */
typedef struct {
    SAN_HEADER;
    double value;
} rt_float_t;

static san_arena_t g_float_arena;

/* 创建浮点值（arena 分配） */
void *rt_float_new(double v) {
    if (!g_float_arena.base) {
        g_float_arena.base = (char*)malloc(65536);
        g_float_arena.used = 0;
        g_float_arena.cap = 65536;
    }
    rt_float_t *f = (rt_float_t *)_arena_alloc(&g_float_arena, sizeof(rt_float_t));
    if (!f) return NULL;
    f->h_type = OBJ_FLOAT;
    f->value = v;
    return f;
}

/* 解包浮点值 */
double rt_unbox_float(void *v) {
    if (!v) return 0.0;
    return ((rt_float_t *)v)->value;
}

/* tagged int 转浮点 */
void *rt_int_to_float(uintptr_t tagged) {
    int64_t val = (int64_t)((intptr_t)tagged >> 1);
    return rt_float_new((double)val);
}

/* ═══════════════════════════════════════════════════════════
 * 列表操作实现
 * 动态数组，cap 不足时 2 倍扩容。
 * ═══════════════════════════════════════════════════════════ */

/* 创建空列表 */
rt_list_t *rt_list_new(void) {
    rt_list_t *lst = (rt_list_t *)calloc(1, sizeof(rt_list_t));
    if (!lst) return NULL;
    lst->h_type = OBJ_LIST;
    lst->cap = 4;
    lst->items = (void **)calloc(4, sizeof(void *));
    return lst;
}

/* 创建指定容量的空列表 */
rt_list_t *rt_list_new_cap(int32_t cap) {
    rt_list_t *lst = (rt_list_t *)calloc(1, sizeof(rt_list_t));
    if (!lst) return NULL;
    if (cap < 4) cap = 4;
    lst->h_type = OBJ_LIST;
    lst->cap = cap;
    lst->items = (void **)calloc((size_t)cap, sizeof(void *));
    return lst;
}

/* 列表追加元素 */
void rt_list_push_item(void *lstp, void *item) {
    rt_list_t *lst = (rt_list_t *)lstp;
    if (!lst) return;
    if (lst->len >= lst->cap) {
        lst->cap *= 2;
        lst->items = realloc(lst->items, (size_t)lst->cap * sizeof(void *));
    }
    lst->items[lst->len++] = item;
}

/* 列表长度 */
int32_t rt_list_len(rt_list_t *lst) { return lst ? lst->len : 0; }

/* 列表取值（越界返回 NULL） */
void *rt_list_get(rt_list_t *lst, int32_t idx) {
    if (!lst || idx < 0 || idx >= lst->len) return NULL;
    return lst->items[idx];
}

/* 列表拼接 */
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

/* 列表切片 [start, end) */
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

/* 字符串转字符列表 */
void *rt_str_to_list(void *s) {
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

/* ═══════════════════════════════════════════════════════════
 * 字典类型（FNV-1a 哈希 + 开放寻址）
 * ═══════════════════════════════════════════════════════════ */
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

/* FNV-1a 哈希 */
static uint32_t _hash_str(const char *s) {
    uint32_t h = 2166136261u;
    for (; *s; s++) {
        h ^= (uint8_t)*s;
        h *= 16777619u;
    }
    return h;
}

/* 字典扩容重哈希 */
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

/* 创建空字典 */
void *rt_dict_new(void) {
    rt_dict_t *d = (rt_dict_t*)calloc(1, sizeof(rt_dict_t));
    if (!d) return NULL;
    d->h_type = OBJ_DICT;
    d->cap = RT_DICT_INIT_CAP;
    d->entries = (rt_entry_t*)calloc(RT_DICT_INIT_CAP, sizeof(rt_entry_t));
    return d;
}

/* 复制键字符串（malloc） */
static char *_strdup_key(const void *kp) {
    const char *s = _cstr(kp);
    if (!s) return NULL;
    size_t len = strlen(s);
    char *d = (char *)malloc(len + 1);
    if (d) memcpy(d, s, len + 1);
    return d;
}

/* 字典键查找（开放寻址），返回索引或 -1 */
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

/* 字典扩容 */
static void _dict_grow(rt_dict_t *d) {
    int32_t new_cap = d->cap * 2;
    if (new_cap < RT_DICT_INIT_CAP) new_cap = RT_DICT_INIT_CAP;
    _dict_resize(d, new_cap);
}

/* 字典包含键检查 */
int32_t rt_dict_contains(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return 0;
    return _dict_find(d, _cstr(kp)) >= 0 ? 1 : 0;
}

/* 字典取值 */
void *rt_dict_get(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return NULL;
    int32_t idx = _dict_find(d, _cstr(kp));
    return idx >= 0 ? d->entries[idx].value : NULL;
}

/* 字典设值（键已存在则覆盖） */
void rt_dict_set(void *dp, void *kp, void *vp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return;
    const char *key = _cstr(kp);
    int32_t idx = _dict_find(d, key);
    if (idx >= 0) {
        d->entries[idx].value = vp;
        return;
    }
    /* 负载因子检查 */
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

/* 从键值对列表批量填充字典 */
void *rt_dict_from_pairs(void *dictp, void *pairs_list) {
    rt_dict_t *d = (rt_dict_t *)dictp;
    rt_list_t *pairs = (rt_list_t *)pairs_list;
    if (!d || !pairs) return dictp;
    for (int32_t i = 0; i + 1 < pairs->len; i += 2) {
        rt_dict_set(d, pairs->items[i], pairs->items[i + 1]);
    }
    return dictp;
}

/* ═══════════════════════════════════════════════════════════
 * 随机数
 * ═══════════════════════════════════════════════════════════ */
static int _rand_ok = 0;

/* 随机整数 [lo, hi] */
int32_t rt_random_int(int32_t lo, int32_t hi) {
    if (!_rand_ok) { srand((unsigned)time(NULL)); _rand_ok = 1; }
    if (lo > hi) { int32_t t = lo; lo = hi; hi = t; }
    return lo + rand() % (hi - lo + 1);
}

/* 随机三态值 (-1, 0, 1) */
int32_t rt_random_trit(void) {
    if (!_rand_ok) { srand((unsigned)time(NULL)); _rand_ok = 1; }
    int r = rand() % 3;
    return r == 0 ? -1 : (r == 1 ? 0 : 1);
}

/* ═══════════════════════════════════════════════════════════
 * 输出
 * ═══════════════════════════════════════════════════════════ */

/* 打印字符串（带换行） */
void rt_print_str(const void *p) {
    if (!p) return;
    printf("%s\n", _cstr(p));
}

/* 打印浮点数 */
void rt_print_float(void *v) {
    if (!v) return;
    printf("%.15g\n", ((rt_float_t *)v)->value);
}

/* ═══════════════════════════════════════════════════════════
 * 等待 / 睡眠
 * ═══════════════════════════════════════════════════════════ */

/* 毫秒级睡眠 */
void rt_sleep(int32_t ms) {
#ifdef _WIN32
    Sleep((DWORD)ms);
#else
    usleep((useconds_t)ms * 1000);
#endif
}

/* ═══════════════════════════════════════════════════════════
 * 文件操作
 * ═══════════════════════════════════════════════════════════ */

/* 读取文件内容为字符串 */
void *rt_read_file(void *path) {
    const char *rp = path ? _cstr(path) : NULL;
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

/* 写入字符串到文件 */
void rt_write_file(void *path, void *content) {
    const char *rp = path ? _cstr(path) : NULL;
    const char *rc = content ? _cstr(content) : NULL;
    if (!rp || !rc) return;
    FILE *f = fopen(rp, "w");
    if (!f) return;
    fwrite(rc, 1, strlen(rc), f);
    fclose(f);
}

/* 读取标准输入 */
void *rt_read_input(void) {
    char buf[4096] = {0};
    if (fgets(buf, sizeof(buf), stdin)) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
        return _rt_make(buf);
    }
    return _rt_make("");
}

/* ═══════════════════════════════════════════════════════════
 * IoT 设备注册表
 * ═══════════════════════════════════════════════════════════ */
#define RT_IOT_MAX 16
typedef struct { char name[32]; int32_t state; } rt_iot_dev_t;
static rt_iot_dev_t _iot_devs[RT_IOT_MAX];
static int32_t _iot_count = 0;

/* 查找或自动注册设备 */
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

/* 设置设备状态（开/关/守/亮/灭） */
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

/* 读取设备状态 */
void *rt_iot_read(void *dp) {
    const char *name = _cstr(dp);
    if (!name) return _rt_make("0");
    rt_iot_dev_t *d = _iot_find(name);
    if (!d) return _rt_make("0");
    char buf[2] = {0};
    snprintf(buf, sizeof(buf), "%d", d->state);
    return _rt_make(buf);
}

/* 查询并打印设备状态 */
void rt_iot_query(void *dp) {
    const char *name = _cstr(dp);
    if (!name) return;
    rt_iot_dev_t *d = _iot_find(name);
    if (d) printf("[IoT] %s = %s\n", d->name, d->state == 1 ? "开" : (d->state == -1 ? "关" : "守"));
}

/* IoT 上下文（桩） */
void rt_iot_with(void *dp, void *bp) { (void)dp; (void)bp; }

/* ═══════════════════════════════════════════════════════════
 * 类型判断
 * ═══════════════════════════════════════════════════════════ */

/* 整数恒真 */
int32_t rt_is_number(int32_t v) { (void)v; return 1; }

/* 字符串判断（非 tagged int 即为字符串） */
int32_t rt_is_string(void *p) {
    if (!p) return 0;
    if ((uintptr_t)p & 1) return 0;  /* tagged int */
    return 1;
}

/* 列表判断（非 tagged int 即为列表） */
int32_t rt_is_list(void *p) {
    if (!p) return 0;
    if ((uintptr_t)p & 1) return 0;  /* tagged int */
    return 1;
}

/* ═══════════════════════════════════════════════════════════
 * 异常处理
 * LLVM codegen 直接 load/store @g_error，rt_throw 仅设置标记。
 * ═══════════════════════════════════════════════════════════ */
void *g_error = NULL;

void rt_throw(void *msg) {
    g_error = msg;
}

/* ═══════════════════════════════════════════════════════════
 * 模块导入（桩）
 * ═══════════════════════════════════════════════════════════ */
void *rt_import(void *path) { (void)path; return _rt_make(""); }
