/* harness.c — 调用编译后的 bootstrap 解析器
 *
 * 编译: gcc harness.c bootstrap.o runtime.o -o sanyan_parse.exe
 *
 * 用法: ./sanyan_parse.exe input.san
 *        echo '(加 1 2)' | ./sanyan_parse.exe
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* 声明 runtime 类型 */
typedef struct {
    int32_t len;
    int32_t cap;
    void **items;
} rt_list_t;

typedef struct {
    int32_t len;
    char data[];
} rt_str_t;

/* 声明 bootstrap 入口（LLVM 编译的 parse_sanyan 函数）*/
extern void *parse_sanyan(const char *source);

/* 递归输出 AST 为 JSON */
static void print_json(void *val) {
    if (val == NULL) {
        printf("null");
        return;
    }
    /* 判断类型：小数值 → int；否则尝试作为字符串或列表 */
    uintptr_t v = (uintptr_t)val;
    if (v < 0x100000) {
        /* 可能是 boxed int */
        printf("%d", (int32_t)(intptr_t)val);
        return;
    }
    /* 尝试作为列表（检查头几个字节是否像 rt_list_t）*/
    rt_list_t *lst = (rt_list_t *)val;
    if (lst->len >= 0 && lst->len < 100000 && lst->cap > 0 && lst->cap < 100000) {
        printf("[");
        for (int32_t i = 0; i < lst->len; i++) {
            if (i > 0) printf(",");
            print_json(lst->items[i]);
        }
        printf("]");
        return;
    }
    /* 当作字符串 */
    rt_str_t *s = (rt_str_t *)val;
    printf("\"");
    for (int32_t i = 0; i < s->len && s->data[i]; i++) {
        char c = s->data[i];
        if (c == '"' || c == '\\') printf("\\%c", c);
        else if (c == '\n') printf("\\n");
        else if (c == '\t') printf("\\t");
        else putchar(c);
    }
    printf("\"");
}

static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    fread(buf, 1, (size_t)sz, f);
    buf[sz] = '\0';
    fclose(f);
    return buf;
}

int main(int argc, char **argv) {
    char *source = NULL;
    int need_free = 0;

    if (argc >= 2) {
        source = read_file(argv[1]);
        if (!source) {
            fprintf(stderr, "无法读取文件: %s\n", argv[1]);
            return 1;
        }
        need_free = 1;
    } else {
        /* 从 stdin 读取 */
        fseek(stdin, 0, SEEK_END);
        long sz = ftell(stdin);
        if (sz <= 0) {
            /* 尝试行读取 */
            char buf[65536];
            size_t total = 0;
            while (fgets(buf + total, (int)(sizeof(buf) - total), stdin))
                total = strlen(buf);
            source = strdup(buf);
            need_free = 1;
        } else {
            fseek(stdin, 0, SEEK_SET);
            source = (char *)malloc((size_t)sz + 1);
            fread(source, 1, (size_t)sz, stdin);
            source[sz] = '\0';
            need_free = 1;
        }
    }

    if (!source || !*source) {
        fprintf(stderr, "无输入\n");
        if (need_free) free(source);
        return 1;
    }

    void *ast = parse_sanyan(source);
    if (ast) {
        print_json(ast);
        printf("\n");
    } else {
        printf("null\n");
    }

    if (need_free) free(source);
    return 0;
}
