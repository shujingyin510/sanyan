/**
 * runtime_common.h — 三言 C 运行时公共类型定义
 *
 * csrc/runtime.c 和 llvmgen/runtime.c 共享的值系统：
 *   - 标记指针编码（intptr_t，32/64 位兼容）
 *   - 堆对象类型枚举
 *   - 字符串/列表/字典结构体定义
 *
 * 用法：在 runtime.c 开头 #include "runtime_common.h"
 */

#ifndef RUNTIME_COMMON_H
#define RUNTIME_COMMON_H

#include <stdint.h>
#include <stddef.h>

/* ═══════════════════════════════════════════════════════════
 * 标记指针值编码
 *
 * 位模式:
 *   (value << 1) | 1  →  整数标记（LSB=1）
 *   heap_ptr           →  堆对象指针（LSB=0）
 *
 * intptr_t 保证 32/64 位平台兼容。
 * ═══════════════════════════════════════════════════════════ */

static inline void *san_tag_i(intptr_t val) {
    return (void*)((intptr_t)((val << 1) | 1));
}

static inline intptr_t san_untag_i(void *p) {
    return (intptr_t)((intptr_t)p >> 1);
}

static inline int san_is_int(void *p) {
    return ((intptr_t)p & 1) != 0;
}

static inline intptr_t san_to_int(void *p) {
    return san_is_int(p) ? san_untag_i(p) : 0;
}

/* csrc 兼容别名 */
#define tag_i   san_tag_i
#define untag_i san_untag_i
#define is_int_val san_is_int
#define to_int  san_to_int

/* llvmgen 兼容别名 */
#define _TAG_I(v)  ((void*)(intptr_t)(((intptr_t)(v) << 1) | 1))
#define _IS_INT(p) (((intptr_t)(p) & 1) != 0)
#define _UNTAG(p)  ((intptr_t)((intptr_t)(p) >> 1))
#define _TO_INT(p) (_IS_INT(p) ? _UNTAG(p) : 0)


/* ═══════════════════════════════════════════════════════════
 * 堆对象类型枚举
 *
 * 统一使用小整数（1-4），csrc 的旧魔数通过兼容宏映射。
 * ═══════════════════════════════════════════════════════════ */

typedef enum {
    OBJ_STRING = 1,
    OBJ_LIST   = 2,
    OBJ_DICT   = 3,
    OBJ_FLOAT  = 4,
    OBJ_TRIT   = 5,  /* 三态对象: value + confidence */
} san_obj_type_t;

/* csrc 兼容：旧版 ObjType 魔数 */
#define TYPE_STR  OBJ_STRING
#define TYPE_LIST OBJ_LIST
#define TYPE_DICT OBJ_DICT
#define ObjType   san_obj_type_t

/* 对象头部宏：两个运行时统一使用 h_type 字段 */
#define SAN_HEADER uint32_t h_type
#define OBJ_HDR    uint32_t h_type


/* ═══════════════════════════════════════════════════════════
 * 字符串类型 (rt_str_t)
 *
 * 格式: [h_type(4)][len(4)][data...]，flexible array member。
 * 两个运行时共享此定义。
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    SAN_HEADER;
    int32_t len;
    char data[];
} rt_str_t;


/* ═══════════════════════════════════════════════════════════
 * 列表类型 (rt_list_t)
 *
 * 格式: [h_type(4)][len(4)][cap(4)][items(ptr)]
 * ═══════════════════════════════════════════════════════════ */

typedef struct rt_list_s {
    SAN_HEADER;
    int32_t len;
    int32_t cap;
    void **items;
} rt_list_t;


/* ═══════════════════════════════════════════════════════════
 * 字典类型（各运行时独立实现，公共头文件只提供常量）
 * ═══════════════════════════════════════════════════════════ */

#define RT_DICT_INIT_CAP    16
#define RT_DICT_LOAD_FACTOR 70  /* 负载因子阈值（百分比） */
#ifndef RT_DICT_MAX_CAP
#define RT_DICT_MAX_CAP     65536  /* 字典最大容量，防止嵌入式系统内存溢出 */
#endif


/* ═══════════════════════════════════════════════════════════
 * 三态值类型 — 紧凑存储: value(1/0/-1) + confidence(0-100)
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    SAN_HEADER;
    int32_t value;
    uint8_t confidence;  /* 0-100, 100 = 1.0 */
} rt_trit_t;

static inline rt_trit_t *rt_trit_new(int32_t val, double conf) {
    rt_trit_t *t = (rt_trit_t *)calloc(1, sizeof(rt_trit_t));
    if (!t) return NULL;
    t->h_type = OBJ_TRIT;
    t->value = (val > 0) ? 1 : ((val < 0) ? -1 : 0);
    t->confidence = (uint8_t)(conf * 100.0);
    if (t->confidence > 100) t->confidence = 100;
    return t;
}


/* ═══════════════════════════════════════════════════════════
 * 浮点类型 (rt_float_t) — IEEE 754 double
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    SAN_HEADER;
    double value;
} rt_float_t;

#ifndef RT_FLOAT_NEW_CUSTOM
static inline rt_float_t *rt_float_new(double v) {
    rt_float_t *f = (rt_float_t *)calloc(1, sizeof(rt_float_t));
    if (!f) return NULL;
    f->h_type = OBJ_FLOAT;
    f->value = v;
    return f;
}
#endif


/* ═══════════════════════════════════════════════════════════
 * 堆对象类型检查辅助
 * ═══════════════════════════════════════════════════════════ */

static inline int san_is_heap_obj(void *p) {
    if (!p || san_is_int(p)) return 0;
    uint32_t t = ((rt_str_t *)p)->h_type;
    return (t == OBJ_STRING || t == OBJ_LIST || t == OBJ_DICT || t == OBJ_FLOAT);
}

static inline int san_is_str(void *p)  { return p && !san_is_int(p) && ((rt_str_t*)p)->h_type == OBJ_STRING; }
static inline int san_is_list(void *p) { return p && !san_is_int(p) && ((rt_str_t*)p)->h_type == OBJ_LIST; }
static inline int san_is_dict(void *p) { return p && !san_is_int(p) && ((rt_str_t*)p)->h_type == OBJ_DICT; }

/* csrc 兼容 */
#define is_heap_obj san_is_heap_obj
#define is_str  san_is_str
#define is_list san_is_list
#define is_dict san_is_dict

/* 获取堆对象类型（h_type 字段），传入非整数值 */
static inline san_obj_type_t san_obj_type(void *p) {
    return (san_obj_type_t)((rt_str_t*)p)->h_type;
}
#define obj_type san_obj_type


/* ═══════════════════════════════════════════════════════════
 * 字符串访问辅助
 *
 * _cstr() 通过校验 h_type ∈ [1,4] 区分 rt_str_t* 与原始 C 字符串。
 * 伪正概率: 4 / 2^32 ≈ 10^(-9)。
 * ═══════════════════════════════════════════════════════════ */

static inline const char *_cstr(const void *p) {
    if (!p) return NULL;
    uint32_t h = ((const rt_str_t *)p)->h_type;
    if (h >= 1 && h <= 4) {
        return ((const rt_str_t *)p)->data;
    }
    return (const char *)p;
}

static inline int32_t _cstr_len(const void *p) {
    if (!p) return 0;
    uint32_t h = ((const rt_str_t *)p)->h_type;
    if (h >= 1 && h <= 4) {
        return ((const rt_str_t *)p)->len;
    }
    return (int32_t)strlen((const char *)p);
}

/* csrc 兼容：rt_str_c 是 _cstr 的别名 */
static inline const char *rt_str_c(void *p) { return _cstr(p); }

/* llvmgen 兼容 */
static inline int32_t rt_str_len(const void *s) { return _cstr_len(s); }


#endif /* RUNTIME_COMMON_H */
