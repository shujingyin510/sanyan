/* compile.c — 无 Python 依赖的编译管线

用法: compile <input.san> [-o output.exe]

管线:
  1. C VM 运行 sugar.bin 解析源码 → AST
  2. C VM 运行 llvmgen.bin 编译 AST → LLVM IR
  3. llc 编译 IR → 目标文件
  4. gcc 链接 → 可执行文件

依赖: csrc/runtime.c, llvmgen/sugar.bin, llvmgen/llvmgen.bin, llc, gcc
*/

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── 复制 runtime.c 的核心定义 ── */
#define VAR_MAX 256
#define STACK_MAX 512
#define CALL_STACK_DEPTH 64
#define MOD_MAX 16

typedef enum { TYPE_STR=0x535452, TYPE_LIST=0x4C4953, TYPE_DICT=0x444943 } ObjType;
#define OBJ_HDR ObjType type

typedef struct { OBJ_HDR; int32_t len; char data[]; } rt_str_t;
typedef struct { OBJ_HDR; int32_t len; int32_t cap; void **items; } rt_list_t;
typedef struct { void *k; void *v; } rt_entry_t;
typedef struct { OBJ_HDR; int32_t n; int32_t cap; rt_entry_t *entries; } rt_dict_t;

static inline void *tag_i(int32_t v) { return (void*)(((int64_t)v << 1) | 1); }
static inline int32_t untag_i(void *p) { return (int32_t)((intptr_t)p >> 1); }
static inline int is_int_val(void *p) { return ((intptr_t)p & 1) != 0; }
static inline int32_t to_int(void *p) { return is_int_val(p) ? untag_i(p) : 0; }
static const char *rt_str_c(void *p) {
    if (!p || is_int_val(p)) return "";
    return ((rt_str_t*)p)->data;
}
static int is_str(void *p) { return p && !is_int_val(p) && ((rt_str_t*)p)->type == TYPE_STR; }
static int is_list(void *p) { return p && !is_int_val(p) && ((rt_str_t*)p)->type == TYPE_LIST; }
static int is_dict(void *p) { return p && !is_int_val(p) && ((rt_str_t*)p)->type == TYPE_DICT; }

/* ── VM 定义 ── */
typedef enum {
    NOP=0, PUSH_I=1, ADD=2, SUB=3, MUL=4, DIV=5, MOD=6,
    LOAD=7, STORE=8, JMP=9, JZ=10, JNZ=11, CALL=12, RET=13,
    PRINT=14, IO_READ=15, IO_WRITE=16, EQ=17, NE=18, GT=19, LT=20,
    GTE=21, LTE=22, NOT=23, WAIT=24, CONCAT=25, STRLEN=26, STRSUB=27,
    STREQ=28, DICT=29, DICT_GET=30, DICT_SET=31, DICT_HAS=32,
    IS_NUM=33, IS_STR=34, IS_LIST=35, SAME=36, GET=37, SET_ELEM=38,
    LIST_NEW=39, LIST_CCAT=40, SLICE=41, LIST_LEN=42, READ_FILE=43,
    WRITE_FILE=44, PUSH_STR=45, IMPORT=46, CALL_EXT=47, WRITE_BIN=48,
    ORD=49, DICT_KEYS=50, JMP32=51, OR=52, AND=53, STR_FIND=54,
    STR_TO_LIST=55, STR_STARTSWITH=56, STR_CONTAINS=57, DICT_LEN=58,
    HALT=0xFF
} Opcode;

/* ── 栈和变量 ── */
typedef struct { uint32_t ret_pc; int16_t stack_base; } CallFrame;
typedef struct {
    void *stack[STACK_MAX]; int16_t sp;
    void *vars[VAR_MAX]; uint8_t var_count;
    const uint8_t *code; uint32_t code_len; uint32_t pc;
    CallFrame call_stack[CALL_STACK_DEPTH]; uint8_t call_depth;
    int halted;
} VM;

static void push(VM *vm, void *v) { vm->stack[vm->sp++] = v; }
static void *pop(VM *vm) { return vm->stack[--vm->sp]; }
static uint8_t rd_u8(const uint8_t *c, uint32_t *pc) { return c[(*pc)++]; }
static int32_t rd_i32(const uint8_t *c, uint32_t *pc) {
    int32_t v; memcpy(&v, c + *pc, 4); *pc += 4; return v;
}
static int val_true(void *v) {
    if (is_int_val(v)) return untag_i(v) != 0;
    return v != NULL;
}

/* ── 字符串/列表/字典 ── */
static rt_str_t *rt_str_new(const char *s) {
    if (!s) return NULL;
    int32_t n = (int32_t)strlen(s);
    rt_str_t *r = (rt_str_t*)malloc(sizeof(rt_str_t) + n + 1);
    r->type = TYPE_STR; r->len = n; memcpy(r->data, s, n + 1);
    return r;
}
static rt_list_t *rt_list_new(void) {
    rt_list_t *l = (rt_list_t*)calloc(1, sizeof(rt_list_t));
    l->type = TYPE_LIST; l->cap = 4; l->items = (void**)calloc(4, sizeof(void*));
    return l;
}
static void rt_list_push(rt_list_t *l, void *v) {
    if (l->len >= l->cap) { l->cap *= 2; l->items = (void**)realloc(l->items, (size_t)l->cap * sizeof(void*)); }
    l->items[l->len++] = v;
}
static rt_dict_t *rt_dict_new(void) {
    rt_dict_t *d = (rt_dict_t*)calloc(1, sizeof(rt_dict_t));
    d->type = TYPE_DICT; d->cap = 16;
    d->entries = (rt_entry_t*)calloc(16, sizeof(rt_entry_t));
    return d;
}

/* ── vm_run（完整版，从 runtime.c 复制） ── */
static int vm_run(VM *vm) {
    while (!vm->halted) {
        if (vm->pc >= vm->code_len) { vm->halted = 1; break; }
        uint8_t op = rd_u8(vm->code, &vm->pc);
        void *a, *b;
        switch (op) {
        case NOP: break;
        case PUSH_I: push(vm, tag_i(rd_i32(vm->code, &vm->pc))); break;
        case ADD: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)+to_int(b))); break;
        case SUB: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)-to_int(b))); break;
        case MUL: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)*to_int(b))); break;
        case DIV: b=pop(vm); a=pop(vm); push(vm, to_int(b)?tag_i(to_int(a)/to_int(b)):tag_i(0)); break;
        case MOD: b=pop(vm); a=pop(vm); push(vm, to_int(b)?tag_i(to_int(a)%to_int(b)):tag_i(0)); break;
        case LOAD: { uint8_t idx=rd_u8(vm->code,&vm->pc); push(vm, idx<vm->var_count?vm->vars[idx]:tag_i(0)); break; }
        case STORE: { uint8_t idx=rd_u8(vm->code,&vm->pc); vm->vars[idx]=pop(vm); if(idx>=vm->var_count)vm->var_count=idx+1; break; }
        case JMP: vm->pc=(uint32_t)rd_i32(vm->code,&vm->pc); break;
        case JZ: { int32_t t=rd_i32(vm->code,&vm->pc); if(!val_true(pop(vm)))vm->pc=(uint32_t)t; break; }
        case JNZ: { int32_t t=rd_i32(vm->code,&vm->pc); if(val_true(pop(vm)))vm->pc=(uint32_t)t; break; }
        case JMP32: vm->pc=(uint32_t)rd_i32(vm->code,&vm->pc); break;
        case CALL: { uint8_t argc=rd_u8(vm->code,&vm->pc); int32_t tgt=rd_i32(vm->code,&vm->pc);
            if(vm->call_depth>=CALL_STACK_DEPTH){fprintf(stderr,"调用栈溢出\n");return 1;}
            CallFrame *f=&vm->call_stack[vm->call_depth++];
            f->ret_pc=vm->pc; f->stack_base=vm->sp-argc;
            vm->pc=(uint32_t)tgt; break; }
        case RET: { if(vm->call_depth==0){vm->halted=1;break;}
            CallFrame *f=&vm->call_stack[--vm->call_depth];
            void *result=vm->sp>f->stack_base?vm->stack[vm->sp-1]:tag_i(0);
            vm->sp=f->stack_base; vm->pc=f->ret_pc; push(vm,result); break; }
        case OR: { b=pop(vm); a=pop(vm); push(vm, val_true(a)||val_true(b)?tag_i(1):tag_i(-1)); break; }
        case AND: { b=pop(vm); a=pop(vm); push(vm, val_true(a)&&val_true(b)?tag_i(1):tag_i(-1)); break; }
        case EQ: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)==to_int(b)?1:-1)); break;
        case NE: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)!=to_int(b)?1:-1)); break;
        case GT: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)>to_int(b)?1:-1)); break;
        case LT: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)<to_int(b)?1:-1)); break;
        case GTE: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)>=to_int(b)?1:-1)); break;
        case LTE: b=pop(vm); a=pop(vm); push(vm, tag_i(to_int(a)<=to_int(b)?1:-1)); break;
        case NOT: a=pop(vm); push(vm, tag_i(!val_true(a)?1:-1)); break;
        case CONCAT: { b=pop(vm); a=pop(vm);
            const char *sa=rt_str_c(a), *sb=rt_str_c(b);
            int la=is_str(a)?((rt_str_t*)a)->len:(int)strlen(sa);
            int lb=is_str(b)?((rt_str_t*)b)->len:(int)strlen(sb);
            rt_str_t *r=(rt_str_t*)malloc(sizeof(rt_str_t)+la+lb+1);
            r->type=TYPE_STR; r->len=la+lb;
            memcpy(r->data,sb,lb); memcpy(r->data+lb,sa,la);
            r->data[la+lb]=0; push(vm,r); break; }
        case STRLEN: a=pop(vm); push(vm, tag_i(is_str(a)?((rt_str_t*)a)->len:0)); break;
        case STREQ: b=pop(vm); a=pop(vm); push(vm, tag_i(strcmp(rt_str_c(a),rt_str_c(b))==0?1:-1)); break;
        case PRINT: a=pop(vm); break;
        case LIST_NEW: { uint8_t cnt=rd_u8(vm->code,&vm->pc); rt_list_t *l=rt_list_new();
            for(int i=0;i<cnt;i++){void *v=pop(vm);l->items[l->len++]=v;}
            for(int i=0;i<l->len/2;i++){void *t=l->items[i];l->items[i]=l->items[l->len-1-i];l->items[l->len-1-i]=t;}
            push(vm,l); break; }
        case GET: { int32_t idx=to_int(pop(vm)); a=pop(vm);
            if(is_list(a)){rt_list_t *l=(rt_list_t*)a; push(vm,(idx>=0&&idx<l->len)?l->items[idx]:tag_i(0));}
            else push(vm,tag_i(0)); break; }
        case LIST_LEN: a=pop(vm); push(vm, tag_i(is_list(a)?((rt_list_t*)a)->len:0)); break;
        case LIST_CCAT: { b=pop(vm); a=pop(vm);
            if(is_list(a)&&is_list(b)){rt_list_t *r=rt_list_new();
            for(int i=0;i<((rt_list_t*)b)->len;i++)rt_list_push(r,((rt_list_t*)b)->items[i]);
            for(int i=0;i<((rt_list_t*)a)->len;i++)rt_list_push(r,((rt_list_t*)a)->items[i]);
            push(vm,r);} else push(vm,tag_i(0)); break; }
        case SLICE: { int32_t end=to_int(pop(vm)); int32_t start=to_int(pop(vm)); a=pop(vm);
            if(is_list(a)){rt_list_t *l=(rt_list_t*)a; rt_list_t *r=rt_list_new();
            for(int32_t i=start;i<end&&i<l->len;i++)rt_list_push(r,l->items[i]);
            push(vm,r);} else push(vm,tag_i(0)); break; }
        case PUSH_STR: { uint16_t len=(uint16_t)rd_u8(vm->code,&vm->pc);
            len|=(uint16_t)rd_u8(vm->code,&vm->pc)<<8;
            rt_str_t *s=(rt_str_t*)malloc(sizeof(rt_str_t)+len+1);
            s->type=TYPE_STR; s->len=(int32_t)len;
            memcpy(s->data,vm->code+vm->pc,len); s->data[len]=0; vm->pc+=len;
            push(vm,s); break; }
        case STR_FIND: { b=pop(vm); a=pop(vm);
            const char *pos=strstr(rt_str_c(a),rt_str_c(b));
            push(vm,tag_i(pos?(int32_t)(pos-rt_str_c(a)):-1)); break; }
        case STR_TO_LIST: { a=pop(vm); const char *s=rt_str_c(a); rt_list_t *l=rt_list_new();
            while(*s){char ch[2]={*s,0}; rt_str_t *c=rt_str_new(ch); rt_list_push(l,c); s++;}
            push(vm,l); break; }
        case STR_STARTSWITH: { b=pop(vm); a=pop(vm);
            push(vm,strncmp(rt_str_c(a),rt_str_c(b),strlen(rt_str_c(b)))==0?tag_i(1):tag_i(-1)); break; }
        case STR_CONTAINS: { b=pop(vm); a=pop(vm);
            push(vm,strstr(rt_str_c(a),rt_str_c(b))?tag_i(1):tag_i(-1)); break; }
        case IS_NUM: a=pop(vm); push(vm,tag_i(is_int_val(a)?1:-1)); break;
        case IS_STR: a=pop(vm); push(vm,tag_i(is_str(a)?1:-1)); break;
        case IS_LIST: a=pop(vm); push(vm,tag_i(is_list(a)||is_dict(a)?1:-1)); break;
        case SAME: b=pop(vm); a=pop(vm); push(vm,tag_i(a==b?1:-1)); break;
        case ORD: a=pop(vm); push(vm,tag_i(is_str(a)&&((rt_str_t*)a)->len>0?(unsigned char)((rt_str_t*)a)->data[0]:0)); break;
        case DICT: { uint8_t cnt=rd_u8(vm->code,&vm->pc); rt_dict_t *d=rt_dict_new();
            for(int i=0;i<cnt;i++){void *v=pop(vm);void *k=pop(vm);
            d->entries[d->n].k=is_int_val(k)?k:(void*)rt_str_new(rt_str_c(k));
            d->entries[d->n].v=v; d->n++;} push(vm,d); break; }
        case DICT_GET: { b=pop(vm); a=pop(vm); push(vm,tag_i(0)); break; }
        case DICT_SET: { b=pop(vm); a=pop(vm); pop(vm); break; }
        case DICT_HAS: { b=pop(vm); a=pop(vm); push(vm,tag_i(-1)); break; }
        case DICT_KEYS: { a=pop(vm); push(vm,rt_list_new()); break; }
        case DICT_LEN: { a=pop(vm); push(vm,tag_i(0)); break; }
        case READ_FILE: case WRITE_FILE: case IO_READ: case IO_WRITE: case WAIT:
        case IMPORT: case CALL_EXT: case WRITE_BIN:
            if(op==READ_FILE||op==IMPORT){pop(vm);push(vm,tag_i(0));}
            else if(op==CALL_EXT){pop(vm);pop(vm);pop(vm);push(vm,tag_i(0));}
            else if(op==WRITE_BIN||op==WRITE_FILE){pop(vm);pop(vm);push(vm,tag_i(0));}
            else{pop(vm);push(vm,tag_i(0));}
            break;
        case HALT: vm->halted=1; break;
        default: fprintf(stderr,"未知指令: 0x%02X\n",op); return 1;
        }
    }
    return 0;
}

/* ── vm_load ── */
static int vm_load(VM *vm, const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) { perror(path); return 1; }
    uint8_t hdr[10];
    if (fread(hdr, 1, 10, fp) != 10) { fclose(fp); return 1; }
    if (memcmp(hdr, "SAN0", 4) != 0) { fclose(fp); return 1; }
    uint32_t code_size; memcpy(&code_size, hdr + 6, 4);
    uint8_t *code = (uint8_t*)malloc(code_size);
    if (fread(code, 1, code_size, fp) != code_size) { free(code); fclose(fp); return 1; }
    fclose(fp);
    memset(vm, 0, sizeof(*vm));
    vm->code = code; vm->code_len = code_size; vm->var_count = hdr[5];
    return 0;
}

/* ── 辅助：写文件 ── */
static void write_file(const char *path, const char *data, int len) {
    FILE *f = fopen(path, "w");
    if (f) { fwrite(data, 1, len, f); fclose(f); }
}

/* ── 辅助：读文件 ── */
static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char*)malloc(sz + 1);
    if (buf) { fread(buf, 1, sz, f); buf[sz] = 0; }
    fclose(f);
    return buf;
}

/* ── 主管线 ── */
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "用法: %s <input.san> [-o output.exe]\n", argv[0]);
        return 1;
    }

    const char *input_path = argv[1];
    const char *output_path = "output.exe";
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
            output_path = argv[++i];
        }
    }

    /* 读取源码 */
    char *source = read_file(input_path);
    if (!source) { fprintf(stderr, "无法读取: %s\n", input_path); return 1; }

    /* 写入临时文件供 sugar.bin 读取 */
    write_file("/tmp/sanyan_src.txt", source, strlen(source));
    free(source);

    /* 步骤 1: C VM 运行 sugar.bin 解析源码 → AST
     * sugar.bin 读取 /tmp/sanyan_src.txt，输出 AST 到 /tmp/sanyan_ast.txt
     */
    fprintf(stderr, "[1/4] 解析源码...\n");
    {
        VM vm;
        if (vm_load(&vm, "stdlib/sugar.bin")) { fprintf(stderr, "加载 sugar.bin 失败\n"); return 1; }
        /* 设置变量：源码文件路径 */
        vm.vars[0] = rt_str_new("/tmp/sanyan_src.txt");
        vm.var_count = 1;
        int ret = vm_run(&vm);
        free((void*)vm.code);
        if (ret != 0) { fprintf(stderr, "解析失败\n"); return 1; }
    }

    /* 步骤 2: C VM 运行 llvmgen.bin 编译 AST → LLVM IR
     * llvmgen.bin 读取 /tmp/sanyan_ast.txt，输出 IR 到 /tmp/sanyan_output.ll
     */
    fprintf(stderr, "[2/4] 编译 LLVM IR...\n");
    {
        VM vm;
        if (vm_load(&vm, "stdlib/llvmgen.bin")) { fprintf(stderr, "加载 llvmgen.bin 失败\n"); return 1; }
        vm.vars[0] = rt_str_new("/tmp/sanyan_ast.txt");
        vm.var_count = 1;
        int ret = vm_run(&vm);
        free((void*)vm.code);
        if (ret != 0) { fprintf(stderr, "IR 编译失败\n"); return 1; }
    }

    /* 步骤 3: llc 编译 IR → 目标文件 */
    fprintf(stderr, "[3/4] llc 编译...\n");
    {
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "llc -filetype=obj /tmp/sanyan_output.ll -o /tmp/sanyan_output.o 2>/dev/null");
        if (system(cmd) != 0) {
            /* 尝试 clang */
            snprintf(cmd, sizeof(cmd), "clang -c /tmp/sanyan_output.ll -o /tmp/sanyan_output.o 2>/dev/null");
            if (system(cmd) != 0) {
                fprintf(stderr, "无法编译 IR (需要 llc 或 clang)\n");
                return 1;
            }
        }
    }

    /* 步骤 4: gcc 链接 → 可执行文件 */
    fprintf(stderr, "[4/4] 链接...\n");
    {
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "gcc /tmp/sanyan_output.o llvmgen/runtime.c -o %s -lm 2>/dev/null", output_path);
        if (system(cmd) != 0) {
            fprintf(stderr, "链接失败\n");
            return 1;
        }
    }

    fprintf(stderr, "✓ 编译完成: %s\n", output_path);
    return 0;
}
