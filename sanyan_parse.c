/* sanyan_parse.c — 三言 S 表达式解析器 (纯 C 移植)
 *
 * 编译为共享库:
 *   gcc -shared -O2 sanyan_parse.c -o sanyan_parse.dll  (Windows)
 *   gcc -shared -O2 sanyan_parse.c -o sanyan_parse.so   (Linux/macOS)
 *
 * Python 调用:
 *   import ctypes, json
 *   lib = ctypes.CDLL('./sanyan_parse.dll')
 *   lib.parse.argtypes = [ctypes.c_char_p]
 *   lib.parse.restype = ctypes.c_char_p
 *   result = lib.parse(source.encode('utf-8'))
 *   ast = json.loads(result.decode('utf-8'))
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── AST 节点类型 ── */
typedef enum { NODE_INT, NODE_STR, NODE_LIST } node_type_t;

typedef struct ast_node {
    node_type_t type;
    union {
        int32_t int_val;
        char *str_val;
        struct { int32_t count; struct ast_node **items; } list;
    };
} ast_node_t;

/* ── 内存池 ── */
static ast_node_t *_pool = NULL;
static int _pool_cap = 0;
static int _pool_len = 0;

static ast_node_t *_alloc_node(void) {
    if (_pool_len >= _pool_cap) {
        _pool_cap = _pool_cap ? _pool_cap * 2 : 256;
        _pool = (ast_node_t *)realloc(_pool, (size_t)_pool_cap * sizeof(ast_node_t));
    }
    ast_node_t *n = &_pool[_pool_len++];
    memset(n, 0, sizeof(ast_node_t));
    return n;
}

static ast_node_t *_make_int(int32_t v) {
    ast_node_t *n = _alloc_node();
    n->type = NODE_INT;
    n->int_val = v;
    return n;
}

static ast_node_t *_make_str(const char *s) {
    ast_node_t *n = _alloc_node();
    n->type = NODE_STR;
    n->str_val = s ? _strdup(s) : NULL;
    return n;
}

static ast_node_t *_make_list(int cap) {
    ast_node_t *n = _alloc_node();
    n->type = NODE_LIST;
    n->list.count = 0;
    n->list.items = (ast_node_t **)calloc((size_t)(cap ? cap : 4), sizeof(ast_node_t *));
    return n;
}

static void _list_add(ast_node_t *lst, ast_node_t *item) {
    lst->list.items[lst->list.count++] = item;
}

/* ── 词法分析 ── */

#define TOKEN_MAX 65536

static char **_tokens = NULL;
static int _token_count = 0;
static char *_token_buf = NULL;
static int _buf_pos = 0;
static int _buf_cap = 0;

static void _add_token(const char *s, int len) {
    if (_token_count >= TOKEN_MAX) return;
    if (_buf_pos + len + 1 > _buf_cap) {
        _buf_cap = _buf_cap ? _buf_cap * 2 : 65536;
        _token_buf = (char *)realloc(_token_buf, (size_t)_buf_cap);
    }
    char *t = _token_buf + _buf_pos;
    memcpy(t, s, (size_t)len);
    t[len] = '\0';
    _buf_pos += len + 1;
    _tokens[_token_count++] = t;
}

static void _add_token_str(const char *s) {
    _add_token(s, (int)strlen(s));
}

static int _try_parse_int(const char *s, int32_t *out) {
    char *end;
    long v = strtol(s, &end, 10);
    if (end != s && *end == '\0') { *out = (int32_t)v; return 1; }
    return 0;
}

static void tokenize(const char *code) {
    _token_count = 0;
    _buf_pos = 0;
    if (!_tokens) {
        _tokens = (char **)calloc(TOKEN_MAX, sizeof(char *));
    } else {
        memset(_tokens, 0, (size_t)TOKEN_MAX * sizeof(char *));
    }
    if (!_token_buf) {
        _buf_cap = 65536;
        _token_buf = (char *)malloc((size_t)_buf_cap);
    }
    _token_buf[0] = '\0';

    int i = 0;
    int len = (int)strlen(code);
    int current_cap = 4096;
    char *current = (char *)malloc((size_t)current_cap);
    int ci = 0;

    while (i < len) {
        unsigned char c = (unsigned char)code[i];

        /* 全角左括号 */
        if (c == 0xEF && i + 2 < len && (unsigned char)code[i + 1] == 0xBC && (unsigned char)code[i + 2] == 0x88) {
            if (ci > 0) { current[ci] = '\0'; _add_token_str(current); ci = 0; }
            _add_token_str("(");
            i += 3; continue;
        }
        /* 全角右括号 */
        if (c == 0xEF && i + 2 < len && (unsigned char)code[i + 1] == 0xBC && (unsigned char)code[i + 2] == 0x89) {
            if (ci > 0) { current[ci] = '\0'; _add_token_str(current); ci = 0; }
            _add_token_str(")");
            i += 3; continue;
        }

        if (c <= 127) {
            /* ASCII 括号 */
            if (c == '(' || c == ')') {
                if (ci > 0) { current[ci] = '\0'; _add_token_str(current); ci = 0; }
                char s[2] = {(char)c, 0};
                _add_token_str(s);
                i++; continue;
            }
            /* 字符串 */
            if (c == '"') {
                if (ci > 0) { current[ci] = '\0'; _add_token_str(current); ci = 0; }
                int j = i + 1;
                while (j < len && code[j] != '"') {
                    if (code[j] == '\\') j++;
                    j++;
                }
                if (j < len) j++;
                _add_token(code + i, j - i);
                i = j; continue;
            }
            /* 空白 */
            if (c == ' ' || c == '\n' || c == '\t' || c == '\r') {
                if (ci > 0) { current[ci] = '\0'; _add_token_str(current); ci = 0; }
                i++; continue;
            }
            /* 普通字符 */
            if (ci >= current_cap - 4) { current_cap *= 2; current = (char *)realloc(current, (size_t)current_cap); }
            current[ci++] = (char)c;
            i++;
        } else {
            /* UTF-8 多字节字符：原样保留 */
            int clen = 1;
            if ((c & 0xE0) == 0xC0) clen = 2;
            else if ((c & 0xF0) == 0xE0) clen = 3;
            else if ((c & 0xF8) == 0xF0) clen = 4;
            for (int k = 0; k < clen && i + k < len; k++) {
                if (ci >= current_cap - 4) { current_cap *= 2; current = (char *)realloc(current, (size_t)current_cap); }
                current[ci++] = code[i + k];
            }
            i += clen;
        }
    }
    if (ci > 0) { current[ci] = '\0'; _add_token_str(current); }
    free(current);
}

/* ── 语法分析 ── */

static int _pos = 0;

static ast_node_t *_parse_expr(void);

static ast_node_t *_parse_list(void) {
    ast_node_t *lst = _make_list(4);
    while (_pos < _token_count && strcmp(_tokens[_pos], ")") != 0) {
        _list_add(lst, _parse_expr());
    }
    if (_pos >= _token_count) {
        /* 括号不匹配，返回已解析的 */
        return lst;
    }
    _pos++; /* skip ')' */
    return lst;
}

static ast_node_t *_parse_expr(void) {
    if (_pos >= _token_count) return _make_str("");
    char *tok = _tokens[_pos++];
    if (strcmp(tok, "(") == 0) {
        return _parse_list();
    }
    if (strcmp(tok, ")") == 0) {
        return _make_str("");
    }
    int32_t iv;
    if (_try_parse_int(tok, &iv)) {
        return _make_int(iv);
    }
    return _make_str(tok);
}

/* ── JSON 序列化 ── */

static int _json_buf_cap = 4096;
static char *_json_buf = NULL;
static int _json_len = 0;

static void _json_write(const char *s) {
    int sl = (int)strlen(s);
    if (!_json_buf) {
        _json_buf_cap = 4096;
        _json_buf = (char *)malloc(_json_buf_cap);
        _json_len = 0;
        _json_buf[0] = '\0';
    }
    while (_json_len + sl + 1 >= _json_buf_cap) {
        _json_buf_cap *= 2;
        _json_buf = (char *)realloc(_json_buf, (size_t)_json_buf_cap);
    }
    memcpy(_json_buf + _json_len, s, (size_t)sl);
    _json_len += sl;
    _json_buf[_json_len] = '\0';
}

static void _json_writec(char c) {
    char s[2] = {c, 0};
    _json_write(s);
}

static void _json_escape(const char *s) {
    _json_writec('"');
    for (int i = 0; s[i]; i++) {
        char c = s[i];
        if (c == '"' || c == '\\') { _json_writec('\\'); _json_writec(c); }
        else if (c == '\n') _json_write("\\n");
        else if (c == '\t') _json_write("\\t");
        else if (c == '\r') _json_write("\\r");
        else _json_writec(c);
    }
    _json_writec('"');
}

static void _json_serialize(ast_node_t *node) {
    if (!node) { _json_write("null"); return; }
    switch (node->type) {
    case NODE_INT: {
        char buf[32];
        snprintf(buf, sizeof(buf), "%d", node->int_val);
        _json_write(buf);
        break;
    }
    case NODE_STR:
        if (node->str_val) _json_escape(node->str_val);
        else _json_write("\"\"");
        break;
    case NODE_LIST:
        _json_writec('[');
        for (int i = 0; i < node->list.count; i++) {
            if (i > 0) _json_write(",");
            _json_serialize(node->list.items[i]);
        }
        _json_writec(']');
        break;
    }
}

/* ── 清理 ── */

static void _cleanup(void) {
    if (_pool) {
        for (int i = 0; i < _pool_len; i++) {
            if (_pool[i].type == NODE_STR && _pool[i].str_val) free(_pool[i].str_val);
            if (_pool[i].type == NODE_LIST && _pool[i].list.items) free(_pool[i].list.items);
        }
        free(_pool); _pool = NULL; _pool_cap = _pool_len = 0;
    }
    if (_json_buf) { free(_json_buf); _json_buf = NULL; _json_buf_cap = 0; _json_len = 0; }
    if (_token_buf) { free(_token_buf); _token_buf = NULL; _buf_cap = 0; _buf_pos = 0; }
    if (_tokens) { free(_tokens); _tokens = NULL; } _token_count = 0;
}

/* ── 公共 API ── */

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT char *sanyan_parse(const char *source) {
    _cleanup();
    tokenize(source);
    _pos = 0;
    ast_node_t *ast = _parse_list(); /* 顶层自动包裹在列表中 */
    _json_serialize(ast);
    return _json_buf ? _json_buf : _strdup("[]");
}

EXPORT void sanyan_free(void *ptr) {
    if (ptr) free(ptr);
}

/* ── 命令行测试 ── */
#ifndef SANYAN_LIB
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "用法: %s input.san\n", argv[0]);
        return 1;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *src = (char *)malloc((size_t)sz + 1);
    fread(src, 1, (size_t)sz, f);
    src[sz] = '\0';
    fclose(f);

    char *json = sanyan_parse(src);
    printf("%s\n", json);
    free(src);
    return 0;
}
#endif
