/* 三言 LLVM 编译运行时库 (libsanyan_rt)
 *
 * 编译:  gcc -c runtime.c -o runtime.o
 *        clang -c runtime.c -o runtime.o  (macOS/Linux)
 *
 * 链接:  clang main.o runtime.o -o a.out
 *
 * 无外部依赖，纯 C99。
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

/* ── 字符串类型 ── */
typedef struct {
    int32_t len;
    char data[];  /* 柔性数组成员，末尾保证 '\\0' */
} rt_str_t;

static rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t len = (int32_t)strlen(s);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + len + 1);
    if (!st) return NULL;
    st->len = len;
    memcpy(st->data, s, len + 1);
    return st;
}

rt_str_t *rt_str_concat(rt_str_t *a, rt_str_t *b) {
    if (!a) return b ? rt_str_new(b->data) : NULL;
    if (!b) return rt_str_new(a->data);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + a->len + b->len + 1);
    if (!st) return NULL;
    st->len = a->len + b->len;
    memcpy(st->data, a->data, a->len);
    memcpy(st->data + a->len, b->data, b->len + 1);
    return st;
}

int32_t rt_str_len(rt_str_t *s) {
    return s ? s->len : 0;
}

rt_str_t *rt_str_substr(rt_str_t *s, int32_t start, int32_t len) {
    if (!s || start < 0 || len <= 0 || start >= s->len)
        return rt_str_new("");
    if (start + len > s->len) len = s->len - start;
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + len + 1);
    if (!st) return NULL;
    st->len = len;
    memcpy(st->data, s->data + start, len);
    st->data[len] = '\0';
    return st;
}

int32_t rt_str_equals(rt_str_t *a, rt_str_t *b) {
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    if (a->len != b->len) return 0;
    return memcmp(a->data, b->data, a->len) == 0 ? 1 : 0;
}

int32_t rt_str_contains(rt_str_t *hs, rt_str_t *ndl) {
    if (!hs || !ndl) return 0;
    return strstr(hs->data, ndl->data) ? 1 : 0;
}

int32_t rt_str_find(rt_str_t *hs, rt_str_t *ndl) {
    if (!hs || !ndl) return -1;
    char *p = strstr(hs->data, ndl->data);
    return p ? (int32_t)(p - hs->data) : -1;
}

rt_str_t *rt_int_to_str(uintptr_t boxed) {
    int32_t val = (int32_t)(intptr_t)boxed;
    char buf[32];
    snprintf(buf, sizeof(buf), "%d", val);
    return rt_str_new(buf);
}

rt_str_t *rt_str_concat_many(int32_t count, ...) {
    /* 变参字符串连接 —— 暂未使用，由编译器两两折叠实现 */
    (void)count;
    return rt_str_new("");
}

/* ── 列表类型 ── */
typedef struct {
    int32_t len;
    int32_t cap;
    void **items;
} rt_list_t;

rt_list_t *rt_list_new(void) {
    rt_list_t *lst = (rt_list_t *)malloc(sizeof(rt_list_t));
    if (!lst) return NULL;
    lst->len = 0;
    lst->cap = 4;
    lst->items = (void **)calloc(lst->cap, sizeof(void *));
    return lst;
}

int32_t rt_list_len(rt_list_t *lst) {
    return lst ? lst->len : 0;
}

void *rt_list_get(rt_list_t *lst, int32_t idx) {
    if (!lst || idx < 0 || idx >= lst->len) return NULL;
    return lst->items[idx];
}

rt_list_t *rt_list_concat(rt_list_t *a, rt_list_t *b) {
    rt_list_t *r = rt_list_new();
    if (!r) return NULL;
    if (a) for (int32_t i = 0; i < a->len; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, r->cap * sizeof(void *)); }
        r->items[r->len++] = a->items[i];
    }
    if (b) for (int32_t i = 0; i < b->len; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, r->cap * sizeof(void *)); }
        r->items[r->len++] = b->items[i];
    }
    return r;
}

rt_list_t *rt_list_slice(rt_list_t *lst, int32_t start, int32_t end) {
    rt_list_t *r = rt_list_new();
    if (!lst || !r) return r;
    if (start < 0) start = 0;
    if (end > lst->len) end = lst->len;
    for (int32_t i = start; i < end; i++) {
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, r->cap * sizeof(void *)); }
        r->items[r->len++] = lst->items[i];
    }
    return r;
}

/* ── 字典类型 ── */
rt_list_t *rt_dict_new(void)   { return rt_list_new(); }
int32_t    rt_dict_contains(rt_list_t *d, rt_str_t *k) { (void)d; (void)k; return 0; }
rt_str_t  *rt_dict_get(rt_list_t *d, rt_str_t *k)     { (void)d; (void)k; return rt_str_new(""); }
void       rt_dict_set(rt_list_t *d, rt_str_t *k, rt_str_t *v) { (void)d; (void)k; (void)v; }

/* ── 类型判断 ── */
int32_t rt_is_number(int32_t v)  { (void)v; return 1; }
int32_t rt_is_string(void *p)    { return p ? 1 : 0; }

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

/* ── 等待（三言 等待 参数为秒，转换为毫秒）── */
void rt_sleep(int32_t sec) {
    int32_t ms = sec * 1000;
#ifdef _WIN32
    Sleep((DWORD)ms);
#else
    usleep((useconds_t)ms * 1000);
#endif
}

/* ── 文件操作 ── */
rt_str_t *rt_read_file(rt_str_t *path) {
    if (!path) return rt_str_new("");
    FILE *f = fopen(path->data, "rb");
    if (!f) return rt_str_new("");
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc(sz + 1);
    if (buf) { fread(buf, 1, (size_t)sz, f); buf[sz] = '\0'; }
    fclose(f);
    rt_str_t *r = rt_str_new(buf ? buf : "");
    free(buf);
    return r;
}

void rt_write_file(rt_str_t *path, rt_str_t *content) {
    if (!path || !content) return;
    FILE *f = fopen(path->data, "w");
    if (!f) return;
    fwrite(content->data, 1, (size_t)content->len, f);
    fclose(f);
}

/* ── 输入 ── */
rt_str_t *rt_read_input(void) {
    char buf[4096] = {0};
    if (fgets(buf, sizeof(buf), stdin)) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
        return rt_str_new(buf);
    }
    return rt_str_new("");
}

/* ── 字符串分割 ── */
rt_list_t *rt_str_split(rt_str_t *s, rt_str_t *sep) {
    rt_list_t *result = rt_list_new();
    if (!s || !sep || sep->len == 0) {
        if (s) {
            if (result->len >= result->cap) { result->cap *= 2; result->items = realloc(result->items, result->cap * sizeof(void *)); }
            result->items[result->len++] = rt_str_new(s->data);
        }
        return result;
    }
    const char *p = s->data, *end = s->data + s->len;
    while (p <= end) {
        const char *f = strstr(p, sep->data);
        if (!f) {
            if (result->len >= result->cap) { result->cap *= 2; result->items = realloc(result->items, result->cap * sizeof(void *)); }
            result->items[result->len++] = rt_str_substr(s, (int32_t)(p - s->data), (int32_t)(end - p));
            break;
        }
        if (f > p) {
            if (result->len >= result->cap) { result->cap *= 2; result->items = realloc(result->items, result->cap * sizeof(void *)); }
            result->items[result->len++] = rt_str_substr(s, (int32_t)(p - s->data), (int32_t)(f - p));
        }
        p = f + sep->len;
    }
    return result;
}

/* ── IoT 桩 ── */
void      rt_iot_set(rt_str_t *d, rt_str_t *s)   { (void)d; (void)s; }
rt_str_t *rt_iot_read(rt_str_t *d)               { (void)d; return rt_str_new("0"); }
void      rt_iot_query(rt_str_t *d)               { printf("[IoT] %s\n", d ? d->data : "?"); }
void      rt_iot_with(rt_str_t *d, rt_str_t *b)   { (void)d; (void)b; }

/* ── 导入桩 ── */
rt_str_t *rt_import(rt_str_t *path)               { (void)path; return rt_str_new(""); }

/* ── 其他桩 ── */
int32_t  rt_is_list(void *p)        { return p != NULL ? 1 : 0; }
rt_str_t *rt_apply_stub(void *fn, void *args) { (void)fn; (void)args; return rt_str_new(""); }
