/* ------------------------------------------------------------
 * Sanyan Level 3 种子 VM -- 最小可审计字节码解释器
 *
 * 设计目标:
 *   零外部依赖(不含 #include)、纯 Linux x86_64 syscall
 *   实现 bytecode_compiler.bin 所需的全部 35 个 opcode
 *   GCC 编译 -> ~7.5KB 原生二进制 -> 人工逐字节可审计
 *
 * 编译: gcc -nostdlib -Os -fno-builtin -lgcc sanyan_vm_seed.c -o sanyan_vm -s
 * 运行: ./sanyan_vm bytecode_compiler.bin
 *
 * 编码: GBK (Windows 中文环境)
 * ------------------------------------------------------------ */
/* ── Linux x86_64 syscall 编号 ── */
#define SYS_read   0
#define SYS_write  1
#define SYS_open   2
#define SYS_close  3
#define SYS_brk   12
#define SYS_exit  60

/* ── 类型 ── */
typedef unsigned int   u32;
typedef   signed int   s32;
typedef unsigned char  u8;
typedef unsigned short u16;
typedef   signed short s16;
typedef unsigned long long u64;

/* ── syscall 包装 ── */
static u64 sys6(u64 n, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6) {
    u64 r;
    __asm__ volatile("movq %1,%%rax; movq %2,%%rdi; movq %3,%%rsi; movq %4,%%rdx; movq %5,%%r10; movq %6,%%r8; movq %7,%%r9; syscall; movq %%rax,%0"
        : "=r"(r) : "r"(n),"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a5),"r"(a6)
        : "rax","rdi","rsi","rdx","r10","r8","r9","memory");
    return r;
}
#define SYS3(n,a,b,c) sys6(n,(u64)(a),(u64)(b),(u64)(c),0,0,0)
#define SYS1(n,a)     sys6(n,(u64)(a),0,0,0,0,0)

/* ── 标记指针 ──
 *   LSB=1 → 整数 (31-bit signed 右移1位)
 *   LSB=0 → 堆对象指针 */
#define TAG(v)     ((void*)(((u64)(v) << 1) | 1))
#define UNTAG(v)   ((s32)((u64)(v) >> 1))
#define IS_INT(v)  (((u64)(v) & 1) != 0)

/* ── 堆对象 ── */
enum { T_STR=1, T_LIST=2, T_DICT=3 };

typedef struct { u32 t; } Obj;
typedef struct { u32 t; u32 len; u8 data[]; } Str;
typedef struct { u32 t; u32 len; u32 cap; void* items[]; } List;
typedef struct { u32 t; u32 cnt; void* kv[]; } Dict;

/* ── 堆: bump 分配器 (brk) ── */
static u8 *hp, *he;
static void* halloc(u32 n) {
    if (!hp) { hp = (u8*)SYS1(SYS_brk,0); he = hp; he = (u8*)SYS1(SYS_brk,(u64)(hp+262144)); }
    u8* p = hp; hp += (n + 7) & ~7;
    if (hp > he) SYS1(SYS_exit, 1);
    return p;
}

/* ── 字符串: UTF-16LE → UTF-8 ── */
static Str* str_from_u16(u8* d, u32 n) {
    u32 nb = 0, i;
    for (i=0; i<n; i++) { u32 cp = d[i*2]|(d[i*2+1]<<8); nb += cp<0x80?1:cp<0x800?2:3; }
    Str* s = halloc(8+nb); s->t=T_STR; s->len=nb;
    u32 p=0;
    for (i=0; i<n; i++) {
        u32 cp = d[i*2]|(d[i*2+1]<<8);
        if (cp<0x80)      { s->data[p++]=(u8)cp; }
        else if (cp<0x800){ s->data[p++]=(u8)(0xC0|(cp>>6)); s->data[p++]=(u8)(0x80|(cp&0x3F)); }
        else              { s->data[p++]=(u8)(0xE0|(cp>>12)); s->data[p++]=(u8)(0x80|((cp>>6)&0x3F)); s->data[p++]=(u8)(0x80|(cp&0x3F)); }
    }
    return s;
}
static s32 str_eq(Str* a, Str* b) { if(a->len!=b->len) return 0; for(u32 i=0;i<a->len;i++) if(a->data[i]!=b->data[i]) return 0; return 1; }
static u32 str_clen(Str* s) { u32 n=0,i=0; while(i<s->len){ i+= (s->data[i]&0x80)?(s->data[i]&0xE0)==0xC0?2:3:1; n++; } return n; }
static Str* str_cat(Str* a, Str* b) { Str* s=halloc(8+a->len+b->len); s->t=T_STR; s->len=a->len+b->len; for(u32 i=0;i<a->len;i++)s->data[i]=a->data[i]; for(u32 i=0;i<b->len;i++)s->data[a->len+i]=b->data[i]; return s; }
static s32 str_cpos(Str* s, u32 ci) { u32 b=0,c=0; while(c<ci&&b<s->len){ b+= (s->data[b]&0x80)?(s->data[b]&0xE0)==0xC0?2:3:1; c++; } return b; }
static Str* str_sub(Str* s, u32 sc, u32 cc) { u32 bs=str_cpos(s,sc); u32 be=bs,c=0; while(c<cc&&be<s->len){ u8 o=s->data[be]; be+= (o&0x80)?(o&0xE0)==0xC0?2:3:1; c++; } u32 nb=be-bs; Str* r=halloc(8+nb); r->t=T_STR; r->len=nb; for(u32 i=0;i<nb;i++)r->data[i]=s->data[bs+i]; return r; }
static s32 str_ord(Str* s, u32 ci) { u32 b=0,c=0; while(c<ci&&b<s->len){ u8 ch=s->data[b]; b+= (ch&0x80)?(ch&0xE0)==0xC0?2:3:1; c++; } if(b>=s->len)return 0; u8 ch=s->data[b]; return (ch&0x80)?(ch&0xE0)==0xC0?((ch&0x1F)<<6)|(s->data[b+1]&0x3F):((ch&0x0F)<<12)|((s->data[b+1]&0x3F)<<6)|(s->data[b+2]&0x3F):ch; }

/* ── 列表 ── */
static List* list_new(u32 n) { List* l=halloc(16+n*8); l->t=T_LIST; l->len=n; l->cap=n; for(u32 i=0;i<n;i++)l->items[i]=0; return l; }
static void* list_get(List* l, u32 i) { return i<l->len?l->items[i]:0; }
static void  list_set(List* l, u32 i, void* v) { if(i<l->len)l->items[i]=v; }
static List* list_cat(List* a, List* b) { u32 n=a->len+b->len; List* r=list_new(n); for(u32 i=0;i<a->len;i++)r->items[i]=a->items[i]; for(u32 i=0;i<b->len;i++)r->items[a->len+i]=b->items[i]; return r; }
static List* list_slice(List* l, u32 s, u32 c) { if(s>=l->len)return list_new(0); if(s+c>l->len)c=l->len-s; List* r=list_new(c); for(u32 i=0;i<c;i++)r->items[i]=l->items[s+i]; return r; }

/* ── 字典 ── */
static s32 key_eq(void* a, void* b) { if(IS_INT(a)&&IS_INT(b))return UNTAG(a)==UNTAG(b); if(!IS_INT(a)&&!IS_INT(b)&&((Obj*)a)->t==T_STR&&((Obj*)b)->t==T_STR)return str_eq((Str*)a,(Str*)b); return 0; }
static Dict* dict_new(u32 n) { Dict* d=halloc(8+n*2*8); d->t=T_DICT; d->cnt=n; for(u32 i=0;i<n*2;i++)d->kv[i]=0; return d; }
static void  dict_set(Dict* d, void* k, void* v) { /* 覆盖已存在的 key */ for(u32 i=0;i<d->cnt*2;i+=2)if(d->kv[i]&&key_eq(d->kv[i],k)){d->kv[i+1]=v;return;} /* 找空位 */ for(u32 i=0;i<d->cnt*2;i+=2)if(!d->kv[i]){d->kv[i]=k;d->kv[i+1]=v;return;} }
static void* dict_get(Dict* d, void* k) { for(u32 i=0;i<d->cnt*2;i+=2)if(d->kv[i]&&key_eq(d->kv[i],k))return d->kv[i+1]; return 0; }
static s32 dict_has(Dict* d, void* k) { for(u32 i=0;i<d->cnt*2;i+=2)if(d->kv[i]&&key_eq(d->kv[i],k))return 1; return 0; }
static List* dict_keys(Dict* d) { u32 n=0,i; for(i=0;i<d->cnt*2;i+=2)if(d->kv[i])n++; List* l=list_new(n); n=0; for(i=0;i<d->cnt*2;i+=2)if(d->kv[i])l->items[n++]=d->kv[i]; return l; }

/* ── VM 状态 ── */
#define SM 512    /* 栈容量 */
#define VM 64     /* 变量数   */
#define CM 65536  /* 代码容量 */
#define CD 64     /* 调用深度 */

static void* stk[SM]; static s32 sp;
static void* var[VM];
static u8    cod[CM]; static u32 cs, pc, halt;
static struct { u32 rpc; void* sv[VM]; s32 ssp; } cstk[CD]; static s32 csp;

/* ── CRT 桩（MinGW 编译器生成的内置函数调用） ── */
void* memset(void* s, int c, unsigned long long n) {
    unsigned char* p = (unsigned char*)s;
    while (n--) *p++ = (unsigned char)c;
    return s;
}
void* memmove(void* d, const void* s, unsigned long long n) {
    unsigned char* dst = (unsigned char*)d;
    const unsigned char* src = (const unsigned char*)s;
    if (dst < src) while (n--) *dst++ = *src++;
    else { dst += n; src += n; while (n--) *--dst = *--src; }
    return d;
}

static void ps(void* v) { if(sp<SM)stk[sp++]=v; }
static void* pp()        { return sp>0?stk[--sp]:0; }

/* ── 文件 I/O ── */
static s32 file_write(Str* path, List* bytes) {
    s32 fd = (s32)SYS3(SYS_open, path->data, 66, 438); /* O_CREAT|O_WRONLY=66, 0666 */
    if (fd < 0) return -1;
    /* 提取字节到临时缓冲区 */
    u8 buf[4096]; u32 n = bytes->len;
    if (n > 4096) n = 4096;
    for (u32 i=0; i<n; i++) buf[i] = (u8)UNTAG(bytes->items[i]);
    SYS3(SYS_write, fd, buf, n);
    SYS1(SYS_close, fd);
    return 0;
}

/* ── 主解释循环 ── */
static void vm_run() {
    while (!halt) {
        if (pc >= cs) { halt=1; break; }
        u8 op = cod[pc++];
        void *a, *b, *r;
        s32 ia, ib;
        u32 n;

        switch (op) {

        case 0x00: break; /* NOP */

        case 0x01: /* PUSH_I — 4B signed LE */
            { s32 v=(s32)(cod[pc]|(cod[pc+1]<<8)|(cod[pc+2]<<16)|(cod[pc+3]<<24)); pc+=4; ps(TAG(v)); } break;

        case 0x2D: /* PUSH_STR — 1B len + len*2B UTF-16LE */
            { u8 l=cod[pc++]; ps(str_from_u16(cod+pc, l)); pc+=l*2; } break;

        case 0x07: /* LOAD — 1B idx */
            { u8 i=cod[pc++]; ps(i<VM?var[i]:0); } break;

        case 0x08: /* STORE — 1B idx */
            { u8 i=cod[pc++]; if(sp>0)var[i]=pp(); } break;

        case 0x02: b=pp(); a=pp(); ps(TAG(UNTAG(a)+UNTAG(b))); break; /* ADD */
        case 0x03: b=pp(); a=pp(); ps(TAG(UNTAG(a)-UNTAG(b))); break; /* SUB */
        case 0x04: b=pp(); a=pp(); ps(TAG(UNTAG(a)*UNTAG(b))); break; /* MUL */
        case 0x05: b=pp(); ib=UNTAG(b); ps(TAG(ib?UNTAG(a)/ib:0)); break; /* DIV */
        case 0x06: b=pp(); ib=UNTAG(b); ps(TAG(ib?UNTAG(a)%ib:0)); break; /* MOD */

        case 0x13: b=pp(); a=pp(); ps(TAG(UNTAG(a)>UNTAG(b)?1:-1)); break; /* GT  */
        case 0x14: b=pp(); a=pp(); ps(TAG(UNTAG(a)<UNTAG(b)?1:-1)); break; /* LT  */
        case 0x15: b=pp(); a=pp(); ps(TAG(UNTAG(a)==UNTAG(b)?1:-1)); break; /* EQ  */
        case 0x17: b=pp(); a=pp(); ps(TAG(UNTAG(a)>=UNTAG(b)?1:-1)); break; /* GTE */

        case 0x19: b=pp(); a=pp(); ps(str_cat((Str*)a,(Str*)b)); break; /* CONCAT */
        case 0x1A: a=pp(); ps(TAG((s32)str_clen((Str*)a))); break; /* STRLEN */
        case 0x1B: b=pp(); a=pp(); r=pp(); ps(str_sub((Str*)r,(u32)UNTAG(a),(u32)UNTAG(b))); break; /* STRSUB */
        case 0x1C: b=pp(); a=pp(); ps(TAG(str_eq((Str*)a,(Str*)b)?1:-1)); break; /* STREQ */
        case 0x31: b=pp(); a=pp(); ps(TAG(str_ord((Str*)a,(u32)UNTAG(b)))); break; /* ORD */

        case 0x27: /* LIST_NEW — 弹 n 个元素建立列表 */
            n = (u32)UNTAG(pp()); { List* l=list_new(n);
            for (u32 i=0; i<n; i++) l->items[n-1-i] = pp();
            ps(l); } break;

        case 0x25: b=pp(); a=pp(); ps(list_get((List*)a,(u32)UNTAG(b))); break; /* LIST_GET */
        case 0x2A: a=pp(); ps(TAG((s32)((List*)a)->len)); break; /* LIST_LEN */
        case 0x26: { void* v=pp(); b=pp(); a=pp(); list_set((List*)a,(u32)UNTAG(b),v); } break; /* SET_ELEMENT */
        case 0x28: b=pp(); a=pp(); ps(list_cat((List*)a,(List*)b)); break; /* LIST_CONCAT */
        case 0x29: b=pp(); a=pp(); r=pp(); ps(list_slice((List*)r,(u32)UNTAG(a),(u32)UNTAG(b))); break; /* SLICE */

        case 0x1D: /* DICT — 弹 n*2 个 k-v 对 */
            n = (u32)UNTAG(pp()); { u32 m=n*2; Dict* d=dict_new(n);
            for (u32 i=0; i<m; i+=2) { void* v=pp(); void* k=pp(); d->kv[m-2-i]=k; d->kv[m-1-i]=v; }
            ps(d); } break;
        case 0x1E: b=pp(); a=pp(); ps(dict_get((Dict*)a,b)); break; /* DICT_GET */
        case 0x1F: { void* v=pp(); b=pp(); a=pp(); dict_set((Dict*)a,b,v); } break; /* DICT_SET */
        case 0x20: b=pp(); a=pp(); ps(TAG(dict_has((Dict*)a,b)?1:-1)); break; /* DICT_HAS */
        case 0x32: a=pp(); ps(dict_keys((Dict*)a)); break; /* DICT_KEYS */

        case 0x21: a=pp(); ps(TAG(IS_INT(a)?1:-1)); break; /* IS_NUM */
        case 0x22: a=pp(); ps(TAG((!IS_INT(a)&&((Obj*)a)->t==T_STR)?1:-1)); break; /* IS_STR */
        case 0x23: a=pp(); ps(TAG((!IS_INT(a)&&((Obj*)a)->t==T_LIST)?1:-1)); break; /* IS_LIST */

        case 0x09: /* JMP — 2B signed offset */
            { s32 off=(s32)(s16)(cod[pc]|(cod[pc+1]<<8)); pc+=2; pc+=off; } break;
        case 0x0A: /* JZ — 2B offset, 栈顶=0时跳 */
            { s32 off=(s32)(s16)(cod[pc]|(cod[pc+1]<<8)); pc+=2;
              if (UNTAG(pp())==0) pc+=off; } break;
        case 0x33: /* JMP32 — 4B signed offset */
            { s32 off=(s32)(cod[pc]|(cod[pc+1]<<8)|(cod[pc+2]<<16)|(cod[pc+3]<<24)); pc+=4; pc+=off; } break;

        case 0x0C: /* CALL — 2B addr, 扫描 STORE 数 arg 数 */
            { u32 ad=(u32)(u16)(cod[pc]|(cod[pc+1]<<8)); pc+=2;
              if (ad&&csp<CD) {
                  u32 ac=0, p=ad;
                  while (p+1<cs && cod[p]==0x08) { ac++; p+=2; }
                  cstk[csp].rpc=pc; cstk[csp].ssp=sp-(s32)ac;
                  for (u32 i=0;i<VM;i++) cstk[csp].sv[i]=var[i];
                  csp++; pc=ad;
              } } break;
        case 0x0D: /* RET — 弹调用帧 */
            if (csp>0) { csp--; pc=cstk[csp].rpc; sp=cstk[csp].ssp;
                         for (u32 i=0;i<VM;i++) var[i]=cstk[csp].sv[i]; }
            else { halt=1; } break;

        case 0x0E: /* PRINT */
            { void* v=pp();
              if (IS_INT(v)) {
                  s32 val=UNTAG(v); u8 neg=0; u8 buf[32]; s32 p=31; buf[p]=0;
                  if (val<0) { neg=1; val=-val; }
                  if (val==0) buf[--p]='0';
                  else while (val>0) { buf[--p]=(u8)(48+(val%10)); val/=10; }
                  if (neg) buf[--p]='-';
                  buf[--p]='\n';
                  SYS3(SYS_write, 1, (u64)(buf+p), (u64)(32-p));
              } else if (!IS_INT(v) && ((Obj*)v)->t==T_STR) {
                  Str* s=(Str*)v; SYS3(SYS_write, 1, (u64)s->data, s->len);
                  SYS3(SYS_write, 1, (u64)n, 1);
              } } break;

        case 0x30: /* WRITE_BINARY — 弹 byte_list, path */
            { void* bl=pp(); void* pt=pp();
              if (bl&&pt&&!IS_INT(bl)&&!IS_INT(pt))
                  file_write((Str*)pt, (List*)bl); } break;

        case 0xFF: halt=1; break; /* HALT */
        default: break; /* 未知 opcode: 安全跳过 */
        }
    }
}

/* ── 加载 .bin ── */
static s32 load(const char* p) {
    s32 fd = (s32)SYS3(SYS_open, (u64)p, 0, 0);
    if (fd<0) return -1;
    u8 h[10]; if (SYS3(SYS_read,fd,h,10)<10) { SYS1(SYS_close,fd); return -1; }
    if (h[0]!='S'||h[1]!='A'||h[2]!='N'||h[3]!='0') { SYS1(SYS_close,fd); return -2; }
    u32 vc=h[5]; for(u32 i=0;i<vc&&i<VM;i++) var[i]=0;
    cs=h[6]|(h[7]<<8)|(h[8]<<16)|(h[9]<<24);
    if (cs>CM) { SYS1(SYS_close,fd); return -3; }
    s32 n=(s32)SYS3(SYS_read,fd,cod,cs);
    SYS1(SYS_close,fd);
    return n;
}

/* ── _start: Linux 原生入口 ──
 *   栈布局: [argc(8B)] [argv[0](8B)] [argv[1](8B)] ...
 *   rsp 指向 argc */
void _start() {
    register u64 sp_reg asm("rsp");
    s32 argc = *(s32*)(sp_reg);
    char** argv = (char**)(sp_reg + 8);

    sp=0; pc=0; halt=0; csp=0;

    if (argc > 1) {
        if (load(argv[1]) < 0) SYS1(SYS_exit, 1);
    } else {
        SYS3(SYS_read, 0, cod, CM); cs=CM;
    }

    vm_run();  /* 初始化代码 (PC=0 → HALT) */
    halt=0;
    vm_run();  /* 主程序 (HALT 之后) */

    SYS1(SYS_exit, 0);
}
