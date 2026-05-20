/* parse_harness.c — 原生解析器 harness: stdin → 解析 → JSON → stdout */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* LLVM 编译的函数 */
extern void *parse_sanyan(const char *source);

/* runtime 类型 */
typedef struct { int32_t len; int32_t cap; void **items; } rt_list_t;
typedef struct { int32_t len; char data[]; } rt_str_t;

static void print_json(void *val, int is_key);

static void print_json_str(const char *s) {
    putchar('"');
    for (int i = 0; s[i]; i++) {
        char c = s[i];
        if (c == '"' || c == '\\') { putchar('\\'); putchar(c); }
        else if (c == '\n') printf("\\n");
        else if (c == '\t') printf("\\t");
        else if (c == '\r') printf("\\r");
        else putchar(c);
    }
    putchar('"');
}

static int is_tagged_int(void *p) {
    return ((uintptr_t)p & 1) != 0;
}

static int is_list_ptr(void *p) {
    if (!p || is_tagged_int(p)) return 0;
    rt_list_t *lst = (rt_list_t *)p;
    return (lst->len >= 0 && lst->len < 100000 && lst->cap > 0 && lst->cap < 100000);
}

static int is_dict_ptr(void *p) {
    (void)p;
    return 0; /* dicts are rare, skip for now */
}

static void print_json_list(rt_list_t *lst, int is_key) {
    putchar('[');
    for (int32_t i = 0; i < lst->len; i++) {
        if (i > 0) printf(",");
        print_json(lst->items[i], 0);
    }
    putchar(']');
}

static void print_json(void *val, int is_key) {
    if (!val) { printf("null"); return; }
    if (is_tagged_int(val)) {
        int32_t v = (int32_t)((intptr_t)val >> 1);
        printf("%d", v);
        return;
    }
    /* try as list */
    if (is_list_ptr(val)) {
        rt_list_t *lst = (rt_list_t *)val;
        print_json_list(lst, is_key);
        return;
    }
    /* assume string */
    rt_str_t *s = (rt_str_t *)val;
    if (s->len > 0 && s->len < 100000 && s->data) {
        print_json_str(s->data);
    } else {
        printf("null");
    }
}

static char *read_all(FILE *f) {
    size_t cap = 4096, len = 0;
    char *buf = (char *)malloc(cap);
    if (!buf) return NULL;
    while (1) {
        size_t n = fread(buf + len, 1, cap - len - 1, f);
        if (n == 0) break;
        len += n;
        if (len + 1 >= cap) {
            cap *= 2;
            buf = (char *)realloc(buf, cap);
        }
    }
    buf[len] = '\0';
    return buf;
}

int main(int argc, char **argv) {
    char *source = NULL;
    int need_free = 0;

    if (argc >= 2) {
        FILE *f = fopen(argv[1], "rb");
        if (!f) { fprintf(stderr, "无法打开: %s\n", argv[1]); return 1; }
        source = read_all(f);
        fclose(f);
        need_free = 1;
    } else {
        source = read_all(stdin);
        need_free = 1;
    }

    if (!source || !*source) {
        printf("null\n");
        if (need_free) free(source);
        return 0;
    }

    void *ast = parse_sanyan(source);
    if (ast) {
        print_json(ast, 0);
    } else {
        printf("null");
    }
    printf("\n");

    if (need_free) free(source);
    return 0;
}
