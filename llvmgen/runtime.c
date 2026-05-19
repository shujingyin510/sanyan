/* 三言 LLVM 编译运行时库 (libsanyan_rt)
 *
 * 所有字符串函数接受 const char*（LLVM 直接传入的全局字符串指针）。
 * 内部包装为 rt_str_t 处理。
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

/* ── 内部字符串类型 ── */
typedef struct {
    int32_t len;
    char data[];
} rt_str_t;

static rt_str_t *_rt_make(const char *s) {
    if (!s) return NULL;
    int32_t len = (int32_t)strlen(s);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + len + 1);
    if (!st) return NULL;
    st->len = len;
    memcpy(st->data, s, len + 1);
    return st;
}

/* ── 字符串 API（全部接受 const char*）── */

void *rt_str_concat(const char *a, const char *b) {
    if (!a && !b) return NULL;
    if (!a) return _rt_make(b);
    if (!b) return _rt_make(a);
    int32_t la = (int32_t)strlen(a), lb = (int32_t)strlen(b);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + la + lb + 1);
    if (!st) return NULL;
    st->len = la + lb;
    memcpy(st->data, a, la);
    memcpy(st->data + la, b, lb + 1);
    return st;
}

int32_t rt_str_len(const char *s)   { return s ? (int32_t)strlen(s) : 0; }

void *rt_str_substr(const char *s, int32_t start, int32_t len) {
    if (!s || start < 0 || len <= 0) return _rt_make("");
    int32_t slen = (int32_t)strlen(s);
    if (start >= slen) return _rt_make("");
    if (start + len > slen) len = slen - start;
    char *buf = (char *)malloc((size_t)len + 1);
    memcpy(buf, s + start, (size_t)len);
    buf[len] = '\0';
    rt_str_t *r = _rt_make(buf);
    free(buf);
    return r;
}

int32_t rt_str_equals(const char *a, const char *b) {
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    return strcmp(a, b) == 0 ? 1 : 0;
}

int32_t rt_str_contains(const char *hs, const char *ndl) {
    if (!hs || !ndl) return 0;
    return strstr(hs, ndl) ? 1 : 0;
}

int32_t rt_str_find(const char *hs, const char *ndl) {
    if (!hs || !ndl) return -1;
    char *p = strstr(hs, ndl);
    return p ? (int32_t)(p - hs) : -1;
}

void *rt_int_to_str(uintptr_t tagged) {
    int32_t val = (int32_t)((intptr_t)tagged >> 1);  /* untag */
    char buf[32];
    snprintf(buf, sizeof(buf), "%d", val);
    return _rt_make(buf);
}

void *rt_str_split(const char *s, const char *sep);

/* ── 列表类型 ── */
typedef struct {
    int32_t len;
    int32_t cap;
    void **items;
} rt_list_t;

rt_list_t *rt_list_new(void) {
    rt_list_t *lst = (rt_list_t *)calloc(1, sizeof(rt_list_t));
    if (!lst) return NULL;
    lst->cap = 4;
    lst->items = (void **)calloc(4, sizeof(void *));
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

/* ── 字典类型 ── */
#define RT_DICT_MAX 64
typedef struct { char *key; void *value; } rt_entry_t;
typedef struct { int32_t count; rt_entry_t entries[RT_DICT_MAX]; } rt_dict_t;

void *rt_dict_new(void) { return calloc(1, sizeof(rt_dict_t)); }

int32_t rt_dict_contains(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return 0;
    for (int32_t i = 0; i < d->count; i++)
        if (d->entries[i].key && strcmp(d->entries[i].key, (const char *)kp) == 0) return 1;
    return 0;
}

void *rt_dict_get(void *dp, void *kp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp) return NULL;
    for (int32_t i = 0; i < d->count; i++)
        if (d->entries[i].key && strcmp(d->entries[i].key, (const char *)kp) == 0) return d->entries[i].value;
    return NULL;
}

void rt_dict_set(void *dp, void *kp, void *vp) {
    rt_dict_t *d = (rt_dict_t *)dp;
    if (!d || !kp || d->count >= RT_DICT_MAX) return;
    for (int32_t i = 0; i < d->count; i++) {
        if (d->entries[i].key && strcmp(d->entries[i].key, (const char *)kp) == 0) {
            d->entries[i].value = vp; return;
        }
    }
    d->entries[d->count].key = _strdup((const char *)kp);
    d->entries[d->count].value = vp;
    d->count++;
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
    FILE *f = fopen(path, "rb");
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
    FILE *f = fopen(path, "w");
    if (!f) return;
    fwrite(content, 1, strlen(content), f);
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
    for (int32_t i = 0; i < _iot_count; i++)
        if (strcmp(_iot_devs[i].name, name) == 0) return &_iot_devs[i];
    if (_iot_count < RT_IOT_MAX) {
        rt_iot_dev_t *d = &_iot_devs[_iot_count++];
        strncpy(d->name, name, 31); d->name[31] = '\0'; d->state = 0;
        return d;
    }
    return NULL;
}

void rt_iot_set(void *dp, void *sp) {
    const char *name = (const char *)dp;
    const char *state = (const char *)sp;
    if (!name) return;
    rt_iot_dev_t *d = _iot_find(name);
    if (!d || !state) return;
    if (strcmp(state, "开") == 0 || strcmp(state, "亮") == 0) d->state = 1;
    else if (strcmp(state, "关") == 0 || strcmp(state, "灭") == 0) d->state = -1;
    else if (strcmp(state, "守") == 0) d->state = 0;
}

void *rt_iot_read(void *dp) {
    const char *name = (const char *)dp;
    if (!name) return _rt_make("0");
    rt_iot_dev_t *d = _iot_find(name);
    if (!d) return _rt_make("0");
    char buf[2] = {0};
    snprintf(buf, sizeof(buf), "%d", d->state);
    return _rt_make(buf);
}

void rt_iot_query(void *dp) {
    const char *name = (const char *)dp;
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

/* ── 异常处理 ── */
static rt_str_t *_rt_error = NULL;
void    rt_try_begin(void)          { _rt_error = NULL; }
int32_t rt_try_check(void)          { return _rt_error != NULL; }
void   *rt_try_get_error(void)      { return _rt_error ? _rt_error->data : NULL; }
void    rt_throw(void *msg)         { _rt_error = (rt_str_t *)msg; }
void    rt_try_end(void)            { _rt_error = NULL; }

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
    if (!s || !r) return r;
    for (int32_t i = 0; s[i]; i++) {
        char buf[2] = {s[i], 0};
        if (r->len >= r->cap) { r->cap *= 2; r->items = realloc(r->items, (size_t)r->cap * sizeof(void *)); }
        r->items[r->len++] = _rt_make(buf);
    }
    return r;
}
