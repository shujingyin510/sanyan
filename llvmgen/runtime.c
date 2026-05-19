/* 三言 LLVM 编译运行时库 (libsanyan_rt)
 *
 * 编译: gcc -c runtime.c -o runtime.o
 * 链接: clang output.o runtime.o -o a.out
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

/* ── 字符串类型 ── */
typedef struct {
    int32_t len;
    char data[];  /* 柔性数组，data[len] = '\0' */
} rt_str_t;

rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t len = (int32_t)strlen(s);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + len + 1);
    st->len = len;
    memcpy(st->data, s, len + 1);
    return st;
}

rt_str_t *rt_str_concat(rt_str_t *a, rt_str_t *b) {
    if (!a) return b ? rt_str_new(b->data) : NULL;
    if (!b) return rt_str_new(a->data);
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + a->len + b->len + 1);
    st->len = a->len + b->len;
    memcpy(st->data, a->data, a->len);
    memcpy(st->data + a->len, b->data, b->len + 1);
    return st;
}

int32_t rt_str_len(rt_str_t *s) {
    return s ? s->len : 0;
}

rt_str_t *rt_str_substr(rt_str_t *s, int32_t start, int32_t len) {
    if (!s || start < 0 || len <= 0 || start >= s->len) {
        return rt_str_new("");
    }
    if (start + len > s->len) len = s->len - start;
    rt_str_t *st = (rt_str_t *)malloc(sizeof(rt_str_t) + len + 1);
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

int32_t rt_str_contains(rt_str_t *haystack, rt_str_t *needle) {
    if (!haystack || !needle) return 0;
    char *p = strstr(haystack->data, needle->data);
    return p ? 1 : 0;
}

int32_t rt_str_find(rt_str_t *haystack, rt_str_t *needle) {
    if (!haystack || !needle) return -1;
    char *p = strstr(haystack->data, needle->data);
    if (!p) return -1;
    return (int32_t)(p - haystack->data);
}

/* ── 字典类型（简化：list of key-value pairs）── */
rt_list_t *rt_dict_new(void) {
    return rt_list_new();  /* dummy: returns empty list */
}

int32_t rt_dict_contains(rt_list_t *d, rt_str_t *key) {
    return 0;  /* dummy */
}

rt_str_t *rt_dict_get(rt_list_t *d, rt_str_t *key) {
    return rt_str_new("");  /* dummy */
}

void rt_dict_set(rt_list_t *d, rt_str_t *key, rt_str_t *val) {
    /* dummy */
}
typedef struct {
    int32_t len;
    int32_t cap;
    void **items;  /* 通用指针数组 */
} rt_list_t;

rt_list_t *rt_list_new(void) {
    rt_list_t *lst = (rt_list_t *)malloc(sizeof(rt_list_t));
    lst->len = 0;
    lst->cap = 4;
    lst->items = (void **)calloc(lst->cap, sizeof(void *));
    return lst;
}

void rt_list_push(rt_list_t *lst, void *item) {
    if (!lst) return;
    if (lst->len >= lst->cap) {
        lst->cap *= 2;
        lst->items = (void **)realloc(lst->items, lst->cap * sizeof(void *));
    }
    lst->items[lst->len++] = item;
}

int32_t rt_list_len(rt_list_t *lst) {
    return lst ? lst->len : 0;
}

void *rt_list_get(rt_list_t *lst, int32_t idx) {
    if (!lst || idx < 0 || idx >= lst->len) return NULL;
    return lst->items[idx];
}

rt_list_t *rt_list_concat(rt_list_t *a, rt_list_t *b) {
    rt_list_t *result = rt_list_new();
    if (a) {
        for (int32_t i = 0; i < a->len; i++)
            rt_list_push(result, a->items[i]);
    }
    if (b) {
        for (int32_t i = 0; i < b->len; i++)
            rt_list_push(result, b->items[i]);
    }
    return result;
}

rt_list_t *rt_list_slice(rt_list_t *lst, int32_t start, int32_t end) {
    rt_list_t *result = rt_list_new();
    if (!lst) return result;
    if (start < 0) start = 0;
    if (end > lst->len) end = lst->len;
    for (int32_t i = start; i < end; i++)
        rt_list_push(result, lst->items[i]);
    return result;
}

/* ── 类型判断 ── */
int32_t rt_is_number(int32_t val) { return 1; }  /* 在 LLVM 后端，一切都是 i32 */
int32_t rt_is_string(void *p) { return p != NULL ? 1 : 0; }
int32_t rt_is_list(void *p) { return p != NULL ? 1 : 0; }

/* ── 输出 ── */
void rt_print_int(int32_t val) {
    printf("%d\n", val);
}

void rt_print_str(rt_str_t *s) {
    if (s) printf("%s\n", s->data);
}

/* ── 字符串分割 ── */
rt_list_t *rt_str_split(rt_str_t *s, rt_str_t *sep) {
    rt_list_t *result = rt_list_new();
    if (!s || !sep || sep->len == 0) {
        if (s) rt_list_push(result, rt_str_new(s->data));
        return result;
    }
    const char *p = s->data;
    const char *end = s->data + s->len;
    while (p <= end) {
        const char *found = strstr(p, sep->data);
        if (!found) {
            rt_list_push(result, rt_str_substr(s, (int32_t)(p - s->data), (int32_t)(end - p)));
            break;
        }
        if (found > p) {
            rt_list_push(result, rt_str_substr(s, (int32_t)(p - s->data), (int32_t)(found - p)));
        }
        p = found + sep->len;
    }
    return result;
}

/* ── 随机数 ── */
static int _rt_rand_seeded = 0;

int32_t rt_random_int(int32_t lo, int32_t hi) {
    if (!_rt_rand_seeded) { srand((unsigned)time(NULL)); _rt_rand_seeded = 1; }
    if (lo > hi) { int32_t t = lo; lo = hi; hi = t; }
    return lo + rand() % (hi - lo + 1);
}

int32_t rt_random_trit(void) {
    if (!_rt_rand_seeded) { srand((unsigned)time(NULL)); _rt_rand_seeded = 1; }
    int r = rand() % 3;
    return r == 0 ? -1 : (r == 1 ? 0 : 1);
}

/* ── 等待 ── */
void rt_sleep(int32_t ms) {
    #ifdef _WIN32
    Sleep(ms);
    #else
    usleep(ms * 1000);
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
    if (buf) {
        fread(buf, 1, sz, f);
        buf[sz] = '\0';
    }
    fclose(f);
    rt_str_t *result = rt_str_new(buf ? buf : "");
    free(buf);
    return result;
}

void rt_write_file(rt_str_t *path, rt_str_t *content) {
    if (!path || !content) return;
    FILE *f = fopen(path->data, "w");
    if (!f) return;
    fwrite(content->data, 1, content->len, f);
    fclose(f);
}

/* ── 输入 ── */
rt_str_t *rt_read_input(void) {
    char buf[4096];
    if (fgets(buf, sizeof(buf), stdin)) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
        return rt_str_new(buf);
    }
    return rt_str_new("");
}

/* ── IoT 设备桩 ── */
void rt_iot_set(rt_str_t *dev, rt_str_t *state) { /* no-op */ }
rt_str_t *rt_iot_read(rt_str_t *dev) { return rt_str_new("0"); }
void rt_iot_query(rt_str_t *dev) { printf("[IoT] query %s\n", dev ? dev->data : "?"); }
void rt_iot_with(rt_str_t *dev, rt_str_t *body_name) { /* no-op */ }

/* ── 导入桩 ── */
rt_str_t *rt_import(rt_str_t *path) { return rt_str_new(\"\"); }

