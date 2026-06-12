/* 三言 LLVM 编译运行时库 (libsanyan_rt)
 *
 * 用途：LLVM 编译产物的 C 运行时（arena 分配器 + 标记指针值系统）
 * 与 csrc/runtime.c 的关系：两者都实现了标记指针值系统和字符串/列表/字典操作。
 *   但本文件额外包含 arena 分配器、浮点支持、HTTP/正则桩函数等。
 *   公共部分（标记指针宏、类型定义）应该在 csrc/runtime_types.h 中统一。
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
#include <winhttp.h>
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
 * 堆对象头部 + 字符串/列表/字典类型定义
 * 已统一到 csrc/runtime_common.h
 * ═══════════════════════════════════════════════════════════ */
#define RT_FLOAT_NEW_CUSTOM  /* 使用 arena 版 rt_float_new */
#include "../csrc/runtime_common.h"

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
/* rt_str_len 已在 runtime_common.h 中定义 */

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
    /* 检查是否为 OBJ_TRIT */
    if (!is_int_val((void*)tagged)) {
        rt_str_t *hdr = (rt_str_t*)tagged;
        if (hdr->h_type == OBJ_TRIT) {
            rt_trit_t *t = (rt_trit_t*)tagged;
            char buf[64];
            snprintf(buf, sizeof(buf), "%d(信度:%.2f)", t->value, t->confidence / 100.0);
            return _rt_make(buf);
        }
    }
    int64_t val = (int64_t)((intptr_t)tagged >> 1);
    char buf[32];
    snprintf(buf, sizeof(buf), "%lld", (long long)val);
    return _rt_make(buf);
}

/* ── 三态值创建与传播 ── */

void *rt_trit_create(int32_t val, double conf) {
    return (void*)rt_trit_new(val, conf);
}

int32_t rt_trit_value(void *trit) {
    if (!trit || is_int_val(trit)) return (int32_t)to_int(trit);
    if (((rt_str_t*)trit)->h_type == OBJ_TRIT)
        return ((rt_trit_t*)trit)->value;
    return 0;
}

double rt_trit_confidence(void *trit) {
    if (!trit || is_int_val(trit)) return 1.0;
    if (((rt_str_t*)trit)->h_type == OBJ_TRIT)
        return ((rt_trit_t*)trit)->confidence / 100.0;
    return 1.0;
}

void *rt_trit_propagate(int32_t result, void *a, void *b) {
    double ca = rt_trit_confidence(a);
    double cb = rt_trit_confidence(b);
    return (void*)rt_trit_new(result, ca * cb);
}

/* ── r_ternary_trit arithmetic runtime functions ── */
void *rt_trit_add(void *a, void *b) {
    return rt_trit_propagate(rt_trit_value(a) + rt_trit_value(b), a, b);
}
void *rt_trit_sub(void *a, void *b) {
    return rt_trit_propagate(rt_trit_value(a) - rt_trit_value(b), a, b);
}
void *rt_trit_mul(void *a, void *b) {
    return rt_trit_propagate(rt_trit_value(a) * rt_trit_value(b), a, b);
}
void *rt_trit_div(void *a, void *b) {
    int32_t bv = rt_trit_value(b);
    return rt_trit_propagate(bv ? rt_trit_value(a) / bv : 0, a, b);
}
void *rt_trit_mod(void *a, void *b) {
    int32_t bv = rt_trit_value(b);
    return rt_trit_propagate(bv ? rt_trit_value(a) % bv : 0, a, b);
}

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
 * URL 解析与 HTTP 客户端（WinHTTP）
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    char host[256];
    char path[1024];
    int port;
    int use_ssl;
} _parsed_url_t;

static int _parse_url(const char *url, _parsed_url_t *pu) {
    memset(pu, 0, sizeof(*pu));
    pu->port = 80;
    pu->use_ssl = 0;
    if (strncmp(url, "https://", 8) == 0) {
        url += 8; pu->use_ssl = 1; pu->port = 443;
    } else if (strncmp(url, "http://", 7) == 0) {
        url += 7;
    }
    const char *hs = url;
    while (*url && *url != ':' && *url != '/' && *url != '?' && *url != '#') url++;
    int hl = (int)(url - hs);
    if (hl <= 0 || hl >= 256) return 0;
    memcpy(pu->host, hs, hl); pu->host[hl] = '\0';
    if (*url == ':') {
        url++; pu->port = 0;
        while (*url >= '0' && *url <= '9') { pu->port = pu->port * 10 + (*url - '0'); url++; }
    }
    if (!*url) {
        strcpy(pu->path, "/");
    } else {
        int pl = 0;
        while (*url && pl < 1023) pu->path[pl++] = *url++;
        pu->path[pl] = '\0';
    }
    return 1;
}

static WCHAR *_u2w(const char *u) {
    int len = MultiByteToWideChar(CP_UTF8, 0, u, -1, NULL, 0);
    WCHAR *w = (WCHAR*)malloc((size_t)len * sizeof(WCHAR));
    if (w) MultiByteToWideChar(CP_UTF8, 0, u, -1, w, len);
    return w;
}

static void *_http_request(const char *url, const char *method, const char *body) {
    if (!url || !*url) return _rt_make("");
    _parsed_url_t pu;
    if (!_parse_url(url, &pu)) return _rt_make("");
    WCHAR *whost = _u2w(pu.host);
    WCHAR *wpath = _u2w(pu.path);
    WCHAR *wmethod = _u2w(method);
    void *ret = _rt_make("");
    HINTERNET hSession = WinHttpOpen(L"Sanyan-LLVM/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, NULL, NULL, 0);
    if (!hSession) goto cleanup_str;
    HINTERNET hConnect = WinHttpConnect(hSession, whost, (INTERNET_PORT)pu.port, 0);
    if (!hConnect) goto cleanup_ses;
    DWORD flags = pu.use_ssl ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, wmethod, wpath, NULL, NULL, NULL, flags);
    if (!hRequest) goto cleanup_conn;
    if (pu.use_ssl) {
        DWORD secure_prot = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2 | WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURE_PROTOCOLS, &secure_prot, sizeof(secure_prot));
    }
    LPVOID body_data = WINHTTP_NO_REQUEST_DATA;
    DWORD body_len = 0;
    if (body) { body_data = (LPVOID)body; body_len = (DWORD)strlen(body); }
    if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, body_data, body_len, body_len, 0))
        goto cleanup_req;
    if (!WinHttpReceiveResponse(hRequest, NULL)) goto cleanup_req;
    char buf[4096];
    char *resp = NULL;
    size_t rlen = 0;
    DWORD read = 0;
    while (WinHttpReadData(hRequest, buf, sizeof(buf) - 1, &read) && read > 0) {
        buf[read] = '\0';
        resp = realloc(resp, rlen + read + 1);
        if (resp) { memcpy(resp + rlen, buf, read); rlen += read; }
    }
    if (resp) { resp[rlen] = '\0'; ret = _rt_make(resp); free(resp); }
cleanup_req:
    WinHttpCloseHandle(hRequest);
cleanup_conn:
    WinHttpCloseHandle(hConnect);
cleanup_ses:
    WinHttpCloseHandle(hSession);
cleanup_str:
    free(whost); free(wpath); free(wmethod);
    return ret;
}

void *rt_http_get(void *url) {
    return _http_request(_cstr(url), "GET", NULL);
}

void *rt_http_post(void *url, void *d) {
    return _http_request(_cstr(url), "POST", _cstr(d));
}

/* ═══════════════════════════════════════════════════════════
 * 正则（桩函数，待完整实现）
 * ═══════════════════════════════════════════════════════════ */
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
 * 浮点类型（rt_float_t 已在 runtime_common.h 定义）
 * 此处仅覆盖 rt_float_new 为 arena 分配版本
 * ═══════════════════════════════════════════════════════════ */

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
/* RT_DICT_INIT_CAP 和 RT_DICT_LOAD_FACTOR 已在 runtime_common.h 中定义 */

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
 * JSON 解析与序列化
 * ═══════════════════════════════════════════════════════════ */

static void _js_ws(const char **p) {
    while (**p == ' ' || **p == '\t' || **p == '\n' || **p == '\r') (*p)++;
}

static void *_js_val(const char **p);

static void *_js_str(const char **p) {
    _js_ws(p);
    if (**p != '"') return _rt_make("");
    (*p)++;
    size_t cap = 64, len = 0;
    char *buf = (char*)malloc(cap);
    while (**p && **p != '"') {
        if (**p == '\\') {
            (*p)++;
            switch (**p) {
                case '"': buf[len++] = '"'; break;
                case '\\': buf[len++] = '\\'; break;
                case 'n': buf[len++] = '\n'; break;
                case 't': buf[len++] = '\t'; break;
                case 'r': buf[len++] = '\r'; break;
                case '/': buf[len++] = '/'; break;
                case 'u': { if (p[1] && p[2] && p[3] && p[4]) { buf[len++] = '?'; (*p) += 4; } break; }
                default: buf[len++] = **p; break;
            }
        } else { buf[len++] = **p; }
        if (len + 4 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
        (*p)++;
    }
    if (**p == '"') (*p)++;
    buf[len] = '\0';
    void *r = _rt_make(buf);
    free(buf);
    return r;
}

static void *_js_num(const char **p) {
    _js_ws(p);
    const char *st = *p;
    int is_float = 0;
    if (**p == '-') (*p)++;
    while (**p >= '0' && **p <= '9') (*p)++;
    if (**p == '.') { is_float = 1; (*p)++; while (**p >= '0' && **p <= '9') (*p)++; }
    if (**p == 'e' || **p == 'E') { is_float = 1; (*p)++; if (**p == '+' || **p == '-') (*p)++; while (**p >= '0' && **p <= '9') (*p)++; }
    int nl = (int)(*p - st);
    char *ns = (char*)malloc((size_t)nl + 1);
    memcpy(ns, st, (size_t)nl); ns[nl] = '\0';
    void *r;
    if (is_float) {
        r = rt_float_new(atof(ns));
    } else {
        int64_t v = (int64_t)atoll(ns);
        r = (void*)(uintptr_t)((v << 1) | 1);
    }
    free(ns);
    return r;
}

static void *_js_arr(const char **p) {
    _js_ws(p);
    if (**p != '[') return NULL;
    (*p)++;
    rt_list_t *lst = rt_list_new();
    _js_ws(p);
    if (**p == ']') { (*p)++; return lst; }
    while (1) {
        rt_list_push_item(lst, _js_val(p));
        _js_ws(p);
        if (**p == ']') { (*p)++; return lst; }
        if (**p == ',') { (*p)++; _js_ws(p); } else break;
    }
    return lst;
}

static void *_js_obj(const char **p) {
    _js_ws(p);
    if (**p != '{') return NULL;
    (*p)++;
    void *d = rt_dict_new();
    _js_ws(p);
    if (**p == '}') { (*p)++; return d; }
    while (1) {
        void *k = _js_str(p);
        _js_ws(p);
        if (**p == ':') (*p)++;
        _js_ws(p);
        void *v = _js_val(p);
        rt_dict_set(d, k, v);
        _js_ws(p);
        if (**p == '}') { (*p)++; return d; }
        if (**p == ',') { (*p)++; _js_ws(p); } else break;
    }
    return d;
}

static void *_js_val(const char **p) {
    _js_ws(p);
    if (**p == '{') return _js_obj(p);
    if (**p == '[') return _js_arr(p);
    if (**p == '"') return _js_str(p);
    if (**p == 't') { if (strncmp(*p, "true", 4) == 0) { *p += 4; return (void*)(uintptr_t)3; } return _rt_make(""); }
    if (**p == 'f') { if (strncmp(*p, "false", 5) == 0) { *p += 5; return (void*)(uintptr_t)1; } return _rt_make(""); }
    if (**p == 'n') { if (strncmp(*p, "null", 4) == 0) { *p += 4; return NULL; } return _rt_make(""); }
    if (**p == '-' || (**p >= '0' && **p <= '9')) return _js_num(p);
    return _rt_make("");
}

void *rt_json_parse(void *s) {
    if (!s) return _rt_make("{}");
    const char *cs = _cstr(s);
    if (!cs || !*cs) return _rt_make("{}");
    return _js_val(&cs);
}

/* ── 序列化 ── */

typedef struct { char *buf; size_t len, cap; } _jb_t;

static void _jb_ap(_jb_t *b, const char *s) {
    size_t sl = strlen(s);
    if (b->len + sl >= b->cap) { b->cap = (b->len + sl) * 2 + 64; b->buf = (char*)realloc(b->buf, b->cap); }
    memcpy(b->buf + b->len, s, sl); b->len += sl;
}

static void _jb_ch(_jb_t *b, char c) {
    if (b->len + 1 >= b->cap) { b->cap = b->cap * 2 + 32; b->buf = (char*)realloc(b->buf, b->cap); }
    b->buf[b->len++] = c;
}

static void _js_val_str(_jb_t *b, void *v);

static void _js_str_str(_jb_t *b, const char *s) {
    _jb_ch(b, '"');
    for (; *s; s++) {
        switch (*s) {
            case '"': _jb_ap(b, "\\\""); break;
            case '\\': _jb_ap(b, "\\\\"); break;
            case '\n': _jb_ap(b, "\\n"); break;
            case '\t': _jb_ap(b, "\\t"); break;
            case '\r': _jb_ap(b, "\\r"); break;
            default: _jb_ch(b, *s); break;
        }
    }
    _jb_ch(b, '"');
}

static void _js_val_str(_jb_t *b, void *v) {
    if (!v) { _jb_ap(b, "null"); return; }
    if ((uintptr_t)v & 1) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%lld", (long long)((intptr_t)v >> 1));
        _jb_ap(b, buf); return;
    }
    uint32_t ht = *(uint32_t*)v;
    if (ht == OBJ_STRING) { _js_str_str(b, _cstr(v)); return; }
    if (ht == OBJ_FLOAT) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%.15g", ((rt_float_t*)v)->value);
        _jb_ap(b, buf); return;
    }
    if (ht == OBJ_LIST) {
        rt_list_t *l = (rt_list_t*)v;
        _jb_ch(b, '[');
        for (int32_t i = 0; i < l->len; i++) {
            if (i > 0) _jb_ch(b, ',');
            _js_val_str(b, l->items[i]);
        }
        _jb_ch(b, ']'); return;
    }
    if (ht == OBJ_DICT) {
        rt_dict_t *d = (rt_dict_t*)v;
        _jb_ch(b, '{');
        int first = 1;
        for (int32_t i = 0; i < d->cap; i++) {
            if (d->entries[i].used) {
                if (!first) _jb_ch(b, ',');
                first = 0;
                _js_str_str(b, d->entries[i].key);
                _jb_ch(b, ':');
                _js_val_str(b, d->entries[i].value);
            }
        }
        _jb_ch(b, '}'); return;
    }
    _jb_ap(b, "null");
}

void *rt_json_stringify(void *v) {
    _jb_t b = {0, 0, 0};
    _js_val_str(&b, v);
    _jb_ch(&b, '\0');
    void *r = _rt_make(b.buf ? b.buf : "");
    free(b.buf);
    return r;
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

/* 打印整数（含三态值） */
void rt_print_int(int32_t v) {
    printf("%d\n", v);
}

/* 打印三态值 */
void rt_print_trit(int32_t v, double conf) {
    if (conf >= 0.999) printf("%d\n", v);
    else printf("%d(信度:%.2f)\n", v, conf);
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
 * 内嵌字节码 VM（用于加载 .bin 模块）
 * ═══════════════════════════════════════════════════════════ */
/* 前向声明 */
void *rt_import(void *path);

/* 标记指针 ── 用 intptr_t 实现 32/64 位兼容 */
#define _TAG_I(v)  ((void*)(intptr_t)(((intptr_t)(v) << 1) | 1))
#define _IS_INT(p) (((intptr_t)(p) & 1) != 0)
#define _UNTAG(p)  ((intptr_t)((intptr_t)(p) >> 1))
#define _TO_INT(p) (_IS_INT(p) ? _UNTAG(p) : 0)

/* 字节码 VM 结构 */
#define _VM_STACK_MAX 4096
#define _VM_CALL_DEPTH 128
#define _BMOD_MAX 32
#define _BEXPORT_MAX 64
#define _BVAR_MAX 256

typedef struct {
    void *stack[_VM_STACK_MAX];
    int32_t sp;
    void *vars[_BVAR_MAX];
    uint8_t var_cnt;
    const uint8_t *code;
    uint32_t code_len;
    uint32_t pc;
    struct { uint32_t ret_pc; int32_t stack_base; } call_stack[_VM_CALL_DEPTH];
    uint8_t call_depth;
    int halted;
} _BVM;

typedef struct {
    const uint8_t *code;
    uint32_t size;
    uint8_t var_cnt;
    void *vars[_BVAR_MAX];
    int export_count;
    char export_names[_BEXPORT_MAX][64];
    uint32_t export_addrs[_BEXPORT_MAX];
} _BModule;

static _BModule _bmods[_BMOD_MAX];
static int _bmod_cnt = 0;

static void _bpush(_BVM *vm, void *v) {
    if (vm->sp >= _VM_STACK_MAX) return;
    vm->stack[vm->sp++] = v;
}
static void *_bpop(_BVM *vm) {
    if (vm->sp <= 0) return _TAG_I(0);
    return vm->stack[--vm->sp];
}

static uint8_t _brd_u8(const uint8_t *c, uint32_t *pc) { return c[(*pc)++]; }
static int32_t _brd_i32(const uint8_t *c, uint32_t *pc) {
    int32_t v; memcpy(&v, c + *pc, 4); *pc += 4; return v;
}
static int16_t _brd_i16(const uint8_t *c, uint32_t *pc) {
    int16_t v; memcpy(&v, c + *pc, 2); *pc += 2; return v;
}

static int _bval_true(void *v) {
    if (_IS_INT(v)) return _UNTAG(v) > 0;
    return v != NULL;
}

/* UTF-16LE 转 UTF-8（模块导出表名 + PUSH_STR 用） */
static char *_butf16_to_utf8(const uint8_t *src, int codepoints) {
    char *out = (char*)malloc((size_t)codepoints * 4 + 1);
    if (!out) return NULL;
    int pos = 0;
    for (int i = 0; i < codepoints; i++) {
        uint32_t cp = src[0] | ((uint32_t)src[1] << 8);
        src += 2;
        if (cp < 0x80) out[pos++] = (char)cp;
        else if (cp < 0x800) {
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

/* 检查 .bin 头部 */
static int _bcheck_hdr(const uint8_t *hdr) {
    if (memcmp(hdr, "SAN0", 4) == 0) return 0;
    if (hdr[0] == 0x53 && hdr[3] == 0x30 && hdr[4] == 0x01) return 0;
    return 1;
}

/* 从已打开文件读取导出表 */
static int _bread_exports(FILE *fp, _BModule *mod) {
    uint8_t buf[2];
    if (fread(buf, 1, 2, fp) != 2) { mod->export_count = 0; return 0; }
    uint16_t cnt;
    memcpy(&cnt, buf, 2);
    if (cnt > _BEXPORT_MAX) cnt = _BEXPORT_MAX;
    mod->export_count = 0;
    for (uint16_t i = 0; i < cnt; i++) {
        if (fread(buf, 1, 2, fp) != 2) break;
        uint16_t nl;
        memcpy(&nl, buf, 2);
        if (nl > 63) nl = 63;
        uint8_t *u16 = (uint8_t*)malloc((size_t)nl * 2);
        if (!u16) break;
        if (fread(u16, 1, (size_t)nl * 2, fp) != (size_t)nl * 2) { free(u16); break; }
        char *u8 = _butf16_to_utf8(u16, nl);
        free(u16);
        if (!u8) break;
        strncpy(mod->export_names[mod->export_count], u8, 63);
        mod->export_names[mod->export_count][63] = '\0';
        free(u8);
        uint8_t addr_buf[4];
        if (fread(addr_buf, 1, 4, fp) != 4) break;
        memcpy(&mod->export_addrs[mod->export_count], addr_buf, 4);
        mod->export_count++;
    }
    return 0;
}

/* 内嵌 VM 主循环 */
static int _bvm_run(_BVM *vm) {
    uint64_t steps = 0;
    while (!vm->halted) {
        if (vm->pc >= vm->code_len) { vm->halted = 1; break; }
        if (++steps > 50000000) { fprintf(stderr, "[rt_import] 超时\n"); return 1; }
        uint8_t op = _brd_u8(vm->code, &vm->pc);
        void *a, *b;
        intptr_t ib;

        switch (op) {
        case 0x00: break; /* NOP */
        case 0x01: _bpush(vm, _TAG_I(_brd_i32(vm->code, &vm->pc))); break; /* PUSH_I */
        case 0x02: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) + _TO_INT(b))); break; /* ADD */
        case 0x03: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) - _TO_INT(b))); break; /* SUB */
        case 0x04: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) * _TO_INT(b))); break; /* MUL */
        case 0x05: b = _bpop(vm); a = _bpop(vm); ib = _TO_INT(b); _bpush(vm, ib ? _TAG_I(_TO_INT(a) / ib) : _TAG_I(0)); break; /* DIV */
        case 0x06: b = _bpop(vm); a = _bpop(vm); ib = _TO_INT(b); _bpush(vm, ib ? _TAG_I(_TO_INT(a) % ib) : _TAG_I(0)); break; /* MOD */

        /* 变量操作 */
        case 0x07: { uint8_t idx = _brd_u8(vm->code, &vm->pc); _bpush(vm, vm->vars[idx]); break; } /* LOAD */
        case 0x08: { uint8_t idx = _brd_u8(vm->code, &vm->pc); vm->vars[idx] = _bpop(vm); break; } /* STORE */

        /* 跳转 */
        case 0x09: { int16_t off = _brd_i16(vm->code, &vm->pc); vm->pc += off; break; } /* JMP */
        case 0x33: { int32_t off = _brd_i32(vm->code, &vm->pc); vm->pc += off; break; } /* JMP32 */
        case 0x0A: { int16_t off = _brd_i16(vm->code, &vm->pc); if (!_bval_true(_bpop(vm))) vm->pc += off; break; } /* JZ */
        case 0x0B: { int16_t off = _brd_i16(vm->code, &vm->pc); if (_bval_true(_bpop(vm))) vm->pc += off; break; } /* JNZ */

        /* 调用 / 返回 */
        case 0x0C: {
            int16_t addr = _brd_i16(vm->code, &vm->pc);
            if (addr == 0) { _bpush(vm, _TAG_I(0)); break; }
            if (vm->call_depth >= _VM_CALL_DEPTH) { fprintf(stderr, "[rt_import] 调用栈溢出\n"); return 1; }
            int32_t arg_count = 0;
            uint32_t p = (uint32_t)addr;
            while (p + 1 < vm->code_len && vm->code[p] == 0x08) { arg_count++; p += 2; }
            vm->call_stack[vm->call_depth].ret_pc = vm->pc;
            vm->call_stack[vm->call_depth].stack_base = vm->sp - arg_count;
            vm->pc = (uint32_t)addr;
            vm->call_depth++;
            break;
        }
        case 0x0D: {
            if (vm->call_depth == 0) { vm->halted = 1; break; }
            vm->call_depth--;
            void *rv = vm->sp > vm->call_stack[vm->call_depth].stack_base ? vm->stack[--vm->sp] : _TAG_I(0);
            vm->sp = vm->call_stack[vm->call_depth].stack_base;
            _bpush(vm, rv);
            vm->pc = vm->call_stack[vm->call_depth].ret_pc;
            break;
        }

        /* 比较 */
        case 0x11: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) == _TO_INT(b) ? 1 : -1)); break;
        case 0x12: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) != _TO_INT(b) ? 1 : -1)); break;
        case 0x13: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) > _TO_INT(b) ? 1 : -1)); break;
        case 0x14: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) < _TO_INT(b) ? 1 : -1)); break;
        case 0x15: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) >= _TO_INT(b) ? 1 : -1)); break;
        case 0x16: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(_TO_INT(a) <= _TO_INT(b) ? 1 : -1)); break;
        case 0x17: a = _bpop(vm); { intptr_t v = _TO_INT(a); _bpush(vm, _TAG_I(v > 0 ? -1 : 1)); } break;

        /* 字符串 */
        case 0x19: { /* CONCAT */
            int32_t n = _TO_INT(_bpop(vm));
            if (n <= 0) { _bpush(vm, _rt_make("")); break; }
            int32_t total = 0;
            int32_t *lens = (int32_t*)malloc((size_t)n * sizeof(int32_t));
            const char **strs = (const char**)malloc((size_t)n * sizeof(char*));
            if (!lens || !strs) { free(lens); free(strs); _bpush(vm, _rt_make("")); break; }
            for (int32_t i = n - 1; i >= 0; i--) {
                void *item = _bpop(vm);
                strs[i] = item ? ((rt_str_t*)item)->data : "";
                lens[i] = (int32_t)strlen(strs[i]);
                total += lens[i];
            }
            rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + total + 1);
            if (!r) { free(lens); free(strs); _bpush(vm, _rt_make("")); break; }
            r->h_type = OBJ_STRING;
            r->len = total;
            char *dst = r->data;
            for (int32_t i = 0; i < n; i++) { memcpy(dst, strs[i], lens[i]); dst += lens[i]; }
            *dst = '\0';
            free(lens); free(strs);
            _bpush(vm, r);
            break;
        }
        case 0x1A: a = _bpop(vm); _bpush(vm, _TAG_I((int32_t)strlen(_IS_INT(a) ? "" : ((rt_str_t*)a)->data))); break;
        case 0x1B: { /* STRSUB */
            int32_t n = _TO_INT(_bpop(vm));
            int32_t st = _TO_INT(_bpop(vm));
            const char *s = a = _bpop(vm); if (a && !_IS_INT(a)) s = ((rt_str_t*)a)->data; else s = "";
            int32_t sl = (int32_t)strlen(s);
            if (st < 0) st = 0;
            if (st > sl) st = sl;
            if (n < 0) n = 0;
            if (st + n > sl) n = sl - st;
            char *buf = (char*)malloc((size_t)n + 1);
            if (buf) { memcpy(buf, s + st, (size_t)n); buf[n] = '\0'; _bpush(vm, _rt_make(buf)); free(buf); }
            else _bpush(vm, _rt_make(""));
            break;
        }
        case 0x1C: b = _bpop(vm); a = _bpop(vm); { /* STREQ */
            const char *sa = a && !_IS_INT(a) ? ((rt_str_t*)a)->data : "";
            const char *sb = b && !_IS_INT(b) ? ((rt_str_t*)b)->data : "";
            _bpush(vm, _TAG_I(strcmp(sa, sb) == 0 ? 1 : -1));
            break;
        }

        /* 输出 */
        case 0x0E: { a = _bpop(vm); /* PRINT - print to stderr for diagnostics */
            if (_IS_INT(a)) fprintf(stderr, "%lld\n", (long long)_UNTAG(a));
            else if (a) fprintf(stderr, "%s\n", ((rt_str_t*)a)->data);
            else fprintf(stderr, "null\n");
            break;
        }

        /* 读写文件 */
        case 0x2B: { /* READ_FILE */
            const char *p = a = _bpop(vm); if (a && !_IS_INT(a)) p = ((rt_str_t*)a)->data; else p = "";
            FILE *f = fopen(p, "rb");
            if (!f) { _bpush(vm, _rt_make("")); break; }
            fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
            char *buf = (char*)malloc((size_t)sz + 1);
            if (!buf) { fclose(f); _bpush(vm, _rt_make("")); break; }
            size_t nr = fread(buf, 1, (size_t)sz, f); fclose(f);
            buf[nr] = '\0';
            _bpush(vm, _rt_make(buf)); free(buf);
            break;
        }
        case 0x2C: { /* WRITE_FILE */
            const char *c = b = _bpop(vm); if (b && !_IS_INT(b)) c = ((rt_str_t*)b)->data; else c = "";
            const char *p = a = _bpop(vm); if (a && !_IS_INT(a)) p = ((rt_str_t*)a)->data; else p = "";
            FILE *f = fopen(p, "wb");
            if (f) { fwrite(c, 1, strlen(c), f); fclose(f); _bpush(vm, _TAG_I(1)); }
            else _bpush(vm, _TAG_I(0));
            break;
        }

        /* 列表 */
        case 0x27: _bpush(vm, rt_list_new()); break; /* LIST_NEW */
        case 0x25: { /* GET */
            int32_t idx = _TO_INT(_bpop(vm));
            a = _bpop(vm);
            if (!a || _IS_INT(a)) { _bpush(vm, _TAG_I(0)); break; }
            rt_list_t *lst = (rt_list_t*)a;
            if (idx < 0 || idx >= lst->len) { _bpush(vm, _TAG_I(0)); break; }
            _bpush(vm, lst->items[idx]); break;
        }
        case 0x26: { /* SET_ELEM */
            void *val = _bpop(vm);
            int32_t idx = _TO_INT(_bpop(vm));
            a = _bpop(vm);
            if (a && !_IS_INT(a)) {
                rt_list_t *lst = (rt_list_t*)a;
                if (idx >= 0 && idx < lst->len) lst->items[idx] = val;
            }
            _bpush(vm, val); break;
        }
        case 0x28: { /* LIST_CCAT */
            b = _bpop(vm); a = _bpop(vm);
            if (!a || _IS_INT(a)) { _bpush(vm, b ? b : _TAG_I(0)); break; }
            if (!b || _IS_INT(b)) { _bpush(vm, a); break; }
            rt_list_t *la = (rt_list_t*)a, *lb = (rt_list_t*)b;
            rt_list_t *res = rt_list_new();
            for (int i = 0; i < la->len; i++) rt_list_push_item(res, la->items[i]);
            for (int i = 0; i < lb->len; i++) rt_list_push_item(res, lb->items[i]);
            _bpush(vm, res); break;
        }
        case 0x29: { /* SLICE */
            int32_t end = _TO_INT(_bpop(vm));
            int32_t st = _TO_INT(_bpop(vm));
            a = _bpop(vm);
            if (!a || _IS_INT(a)) { _bpush(vm, rt_list_new()); break; }
            rt_list_t *lst = (rt_list_t*)a;
            if (st < 0) st = 0;
            if (st > lst->len) st = lst->len;
            if (end > lst->len) end = lst->len;
            if (end < st) end = st;
            rt_list_t *res = rt_list_new();
            for (int i = st; i < end; i++) rt_list_push_item(res, lst->items[i]);
            _bpush(vm, res); break;
        }
        case 0x2A: a = _bpop(vm); /* LIST_LEN */
            _bpush(vm, _TAG_I(a && !_IS_INT(a) ? ((rt_list_t*)a)->len : 0)); break;

        /* 字典 */
        case 0x1D: _bpush(vm, rt_dict_new()); break; /* DICT */
        case 0x1E: { /* DICT_GET */
            void *key = _bpop(vm);
            a = _bpop(vm);
            if (!a || _IS_INT(a)) { _bpush(vm, _TAG_I(0)); break; }
            _bpush(vm, rt_dict_get(a, key)); break;
        }
        case 0x1F: { /* DICT_SET */
            void *val = _bpop(vm);
            void *key = _bpop(vm);
            a = _bpop(vm);
            if (a && !_IS_INT(a)) rt_dict_set(a, key, val);
            _bpush(vm, val); break;
        }
        case 0x20: { /* DICT_HAS */
            void *key = _bpop(vm);
            a = _bpop(vm);
            _bpush(vm, _TAG_I(a && !_IS_INT(a) && rt_dict_contains(a, key) ? 1 : -1)); break;
        }
        case 0x32: { /* DICT_KEYS */
            a = _bpop(vm);
            if (!a || _IS_INT(a)) { _bpush(vm, rt_list_new()); break; }
            rt_dict_t *d = (rt_dict_t*)a;
            rt_list_t *kl = rt_list_new();
            for (int32_t i = 0; i < d->cap; i++) {
                if (d->entries[i].used) {
                    rt_list_push_item(kl, _rt_make(d->entries[i].key));
                }
            }
            _bpush(vm, kl); break;
        }
        case 0x3A: a = _bpop(vm); /* DICT_LEN */
            _bpush(vm, _TAG_I(0)); break; /* 简化实现 */

        /* 字符串查找 */
        case 0x36: { /* STR_FIND */
            b = _bpop(vm); a = _bpop(vm);
            const char *hs = a && !_IS_INT(a) ? ((rt_str_t*)a)->data : "";
            const char *nd = b && !_IS_INT(b) ? ((rt_str_t*)b)->data : "";
            const char *f = strstr(hs, nd);
            _bpush(vm, _TAG_I(f ? (int32_t)(f - hs) : -1)); break;
        }
        case 0x37: { /* STR_TO_LIST */
            a = _bpop(vm);
            const char *s = a && !_IS_INT(a) ? ((rt_str_t*)a)->data : "";
            rt_list_t *lst = rt_list_new();
            while (*s) { char tmp[2] = {*s++, 0}; rt_list_push_item(lst, _rt_make(tmp)); }
            _bpush(vm, lst); break;
        }
        case 0x38: { /* STR_STARTSWITH */
            b = _bpop(vm); a = _bpop(vm);
            const char *s = a && !_IS_INT(a) ? ((rt_str_t*)a)->data : "";
            const char *pre = b && !_IS_INT(b) ? ((rt_str_t*)b)->data : "";
            size_t pl = strlen(pre);
            _bpush(vm, _TAG_I(strncmp(s, pre, pl) == 0 ? 1 : -1)); break;
        }
        case 0x39: { /* STR_CONTAINS */
            b = _bpop(vm); a = _bpop(vm);
            const char *hs = a && !_IS_INT(a) ? ((rt_str_t*)a)->data : "";
            const char *nd = b && !_IS_INT(b) ? ((rt_str_t*)b)->data : "";
            _bpush(vm, _TAG_I(strstr(hs, nd) != NULL ? 1 : -1)); break;
        }

        /* 类型检查 */
        case 0x21: a = _bpop(vm); _bpush(vm, _TAG_I(_IS_INT(a) ? 1 : -1)); break;
        case 0x22: a = _bpop(vm); _bpush(vm, _TAG_I(!a || _IS_INT(a) ? -1 : 1)); break;
        case 0x23: a = _bpop(vm); _bpush(vm, _TAG_I(!a || _IS_INT(a) ? -1 : 1)); break;
        case 0x24: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I(a == b ? 1 : -1)); break;

        /* 字符串 push（UTF-16LE in bytecode） */
        case 0x2D: {
            int len = _brd_u8(vm->code, &vm->pc);
            char *u8 = _butf16_to_utf8(vm->code + vm->pc, len);
            vm->pc += len * 2;
            _bpush(vm, _rt_make(u8 ? u8 : ""));
            free(u8);
            break;
        }

        /* 逻辑或/与 */
        case 0x34: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I((_TO_INT(a) || _TO_INT(b)) ? 1 : -1)); break;
        case 0x35: b = _bpop(vm); a = _bpop(vm); _bpush(vm, _TAG_I((_TO_INT(a) && _TO_INT(b)) ? 1 : -1)); break;

        /* 等待/睡眠 */
        case 0x18: {
            int32_t ms = _TO_INT(_bpop(vm));
#ifdef _WIN32
            Sleep(ms);
#else
            struct timespec ts = {ms / 1000, (ms % 1000) * 1000000L};
            nanosleep(&ts, NULL);
#endif
            break;
        }

        /* 模块导入（递归） */
        case 0x2E: {
            void *pval = _bpop(vm);
            _bpush(vm, rt_import(pval));
            break;
        }

        case 0xFF: vm->halted = 1; break; /* HALT */
        default:
            fprintf(stderr, "[rt_import] 未知操作码 0x%02X at pc=%u\n", op, vm->pc - 1);
            return 1;
        }
    }
    return 0;
}

/* 获取 .bin 路径（尝试 path.san → path.bin 自动转换） */
static char *_bresolve_path(const char *path) {
    if (!path) return NULL;
    size_t pl = strlen(path);
    if (pl >= 4 && strcmp(path + pl - 4, ".bin") == 0) return _rt_make(path) ? strdup(path) : NULL;
    /* 尝试 path.bin、stdlib/path.bin */
    char buf1[512], buf2[512], buf3[512];
    snprintf(buf1, sizeof(buf1), "%s.bin", path);
    if (pl >= 4 && strcmp(path + pl - 4, ".san") == 0) {
        snprintf(buf1, sizeof(buf1), "%s", path);
        size_t bl = strlen(buf1);
        if (bl >= 4) memcpy(buf1 + bl - 4, ".bin", 4);
    }
    snprintf(buf2, sizeof(buf2), "stdlib/%s.bin", path);
    if (pl >= 4 && strcmp(path + pl - 4, ".san") == 0) {
        snprintf(buf2, sizeof(buf2), "stdlib/%s", path);
        size_t bl2 = strlen(buf2);
        if (bl2 >= 4) memcpy(buf2 + bl2 - 4, ".bin", 4);
    }
    if (path[0] != '/' && path[0] != '\\' && !strchr(path, ':')) {
        snprintf(buf3, sizeof(buf3), "stdlib/%s", path);
    }
    for (int i = 0; i < 3; i++) {
        const char *cp = i == 0 ? buf1 : (i == 1 ? buf2 : buf3);
        if (!cp || !*cp) continue;
        FILE *f = fopen(cp, "rb");
        if (f) { fclose(f); return strdup(cp); }
    }
    return NULL;
}

/* ═══════════════════════════════════════════════════════════
 * 模块导入（真实实现）
 * ═══════════════════════════════════════════════════════════ */
void *rt_import(void *path) {
    if (!path || _IS_INT(path)) return _rt_make("");
    const char *path_str = ((rt_str_t*)path)->data;
    if (!path_str || !*path_str) return _rt_make("");

    char *bin_path = _bresolve_path(path_str);
    if (!bin_path) return _rt_make("");

    FILE *f = fopen(bin_path, "rb");
    if (!f) { free(bin_path); return _rt_make(""); }

    uint8_t hdr[10];
    if (fread(hdr, 1, 10, f) != 10 || _bcheck_hdr(hdr)) {
        fclose(f); free(bin_path); return _rt_make("");
    }

    uint32_t sz;
    memcpy(&sz, hdr + 6, 4);
    uint8_t *code = (uint8_t*)malloc(sz);
    if (!code) { fclose(f); free(bin_path); return _rt_make(""); }
    if (fread(code, 1, sz, f) != sz) {
        free(code); fclose(f); free(bin_path); return _rt_make("");
    }

    int mid = _bmod_cnt;
    if (mid >= _BMOD_MAX) { free(code); fclose(f); free(bin_path); return _TAG_I(0); }

    _bmods[mid].code = code;
    _bmods[mid].size = sz;
    _bmods[mid].var_cnt = hdr[5];
    memset(_bmods[mid].vars, 0, sizeof(void*) * _BVAR_MAX);
    _bmods[mid].export_count = 0;
    _bread_exports(f, &_bmods[mid]);
    fclose(f);

    /* 执行模块初始化代码 */
    {
        _BVM init_vm;
        memset(&init_vm, 0, sizeof(init_vm));
        init_vm.code = code;
        init_vm.code_len = sz;
        init_vm.var_cnt = hdr[5];
        _bvm_run(&init_vm);
        memcpy(_bmods[mid].vars, init_vm.vars, sizeof(void*) * _BVAR_MAX);
        _bmod_cnt++;
    }

    free(bin_path);
    return _TAG_I(mid + 1);  /* 返回模块 ID（1-based，0 表示无效） */
}

/* 跨模块函数调用 */
void *rt_module_call(void *mod_handle, void *func_name, void *arg_list) {
    if (!mod_handle || _IS_INT(mod_handle)) return _TAG_I(0);
    int32_t mid = _UNTAG(mod_handle) - 1;
    if (mid < 0 || mid >= _bmod_cnt) return _TAG_I(0);
    const char *fname = func_name && !_IS_INT(func_name) ? ((rt_str_t*)func_name)->data : "";
    _BModule *mod = &_bmods[mid];
    for (int i = 0; i < mod->export_count; i++) {
        if (strcmp(mod->export_names[i], fname) == 0) {
            uint32_t addr = mod->export_addrs[i];
            _BVM call_vm;
            memset(&call_vm, 0, sizeof(call_vm));
            call_vm.code = mod->code;
            call_vm.code_len = mod->size;
            call_vm.var_cnt = mod->var_cnt;
            memcpy(call_vm.vars, mod->vars, sizeof(void*) * _BVAR_MAX);
            /* 压入参数 */
            if (arg_list && !_IS_INT(arg_list)) {
                rt_list_t *lst = (rt_list_t*)arg_list;
                for (int j = lst->len - 1; j >= 0; j--) _bpush(&call_vm, lst->items[j]);
            }
            /* 压入函数地址并执行 CALL */
            call_vm.pc = addr;
            _bvm_run(&call_vm);
            return call_vm.sp > 0 ? call_vm.stack[call_vm.sp - 1] : _TAG_I(0);
        }
    }
    return _TAG_I(0);
}
