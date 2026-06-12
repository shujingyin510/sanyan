; ═══════════════════════════════════════════════════════════════
; Sanyan Level 4 种子 VM — 手写 x86_64 ELF64 汇编
;
; 源码: ~700 行 NASM，中文逐行注释
; 汇编: nasm -f bin -o sanyan_vm sanyan_vm_l4.asm
; 产出一体化 ELF64 可执行文件，~3KB
; 审计: objdump -d -M intel sanyan_vm → 逐指令可读
;
; 寄存器: r8=sp, r9=pc, r10=code, r11=code_len, r12=vars, r13=stack
;         r14=csp, r15=cstk
; ═══════════════════════════════════════════════════════════════

BITS 64

; ── ELF64 头 ──
org 0
ehdr:
    db 0x7F,'E','L','F'    ; magic
    db 2, 1, 1, 0          ; class=64, data=LE, ver=1, ABI=SysV
    times 8 db 0
    dw 2                    ; ET_EXEC
    dw 0x3E                 ; x86-64
    dd 1                    ; version
    dq _start               ; entry
    dq phdr - ehdr          ; phoff
    dq 0                    ; shoff
    dd 0                    ; flags
    dw 64                   ; ehsize
    dw 56                   ; phentsize
    dw 1                    ; phnum
    dw 0                    ; shentsize
    dw 0                    ; shnum
    dw 0                    ; shstrndx

; ── Program Header (PT_LOAD, RWX) ──
phdr:
    dd 1                    ; PT_LOAD
    dd 7                    ; flags: R|W|X
    dq 0                    ; offset
    dq ehdr                 ; vaddr
    dq ehdr                 ; paddr
    dq file_end             ; filesz
    dq mem_end              ; memsz (含 BSS)
    dq 0x1000               ; align

; ═══════════════════════════════════════════════════════════
; 入口 — 解析 argc/argv（Linux 栈: [argc][argv[0]]...[NULL]）
; ═══════════════════════════════════════════════════════════
_start:
    pop rcx                 ; argc
    mov rsi, rsp            ; argv (rsp 指向 argv[0] 之后)
    lea r13, [rel stack]    ; 栈数组基址
    xor r8d, r8d            ; sp = 0
    lea r12, [rel vars]     ; 变量数组
    lea r15, [rel cstk]     ; 调用栈
    xor r14d, r14d          ; csp = 0
    mov byte [rel halted], 0

    ; 若 argc > 1: 从 argv[1] 加载 .bin
    cmp rcx, 1
    jle .stdin

    mov rdi, [rsi + 8]      ; argv[1] = 路径
    call load_bin
    test eax, eax
    js  .exit1
    jmp .run

.stdin:
    ; read(0, code_buf, 65536)
    mov eax, 0; mov edi, 0; lea rsi, [rel code_buf]; mov edx, 0x10000; syscall
    mov [rel code_len], eax
    cmp eax, 0
    jle .exit1

.run:
    ; 初始化执行 (pc=0 → HALT)
    xor r9d, r9d
    lea r10, [rel code_buf]
    mov r11d, [rel code_len]
    mov byte [rel halted], 0
    call dispatch

    ; 主程序执行 (HALT 之后)
    mov byte [rel halted], 0
    call dispatch

    xor edi, edi
    mov eax, 60; syscall    ; exit(0)

.exit1:
    mov edi, 1
    mov eax, 60; syscall

; ═══════════════════════════════════════════════════════════
; dispatch — 主循环: 取指 → 解码 → 执行
;   r8=sp, r9=pc, r10=code, r11=code_len, r12=vars, r13=stack
;   r14=csp, r15=cstk
; ═══════════════════════════════════════════════════════════
dispatch:
    cmp byte [rel halted], 0
    jne .done
    cmp r9d, r11d
    jae .halt

    movzx eax, byte [r10 + r9]
    inc r9

    cmp al, 0x00; je dispatch      ; NOP
    cmp al, 0xFF; je .halt          ; HALT
    cmp al, 0x01; je do_PUSH_I
    cmp al, 0x2D; je do_PUSH_STR
    cmp al, 0x07; je do_LOAD
    cmp al, 0x08; je do_STORE
    cmp al, 0x02; je do_ADD
    cmp al, 0x03; je do_SUB
    cmp al, 0x04; je do_MUL
    cmp al, 0x05; je do_DIV
    cmp al, 0x06; je do_MOD
    cmp al, 0x13; je do_GT
    cmp al, 0x14; je do_LT
    cmp al, 0x15; je do_EQ
    cmp al, 0x17; je do_GTE
    cmp al, 0x19; je do_CONCAT
    cmp al, 0x1A; je do_STRLEN
    cmp al, 0x1B; je do_STRSUB
    cmp al, 0x1C; je do_STREQ
    cmp al, 0x31; je do_ORD
    cmp al, 0x27; je do_LIST_NEW
    cmp al, 0x25; je do_LIST_GET
    cmp al, 0x2A; je do_LIST_LEN
    cmp al, 0x26; je do_SET_ELEM
    cmp al, 0x28; je do_LIST_CAT
    cmp al, 0x29; je do_SLICE
    cmp al, 0x1D; je do_DICT
    cmp al, 0x1E; je do_DICT_GET
    cmp al, 0x1F; je do_DICT_SET
    cmp al, 0x20; je do_DICT_HAS
    cmp al, 0x32; je do_DICT_KEYS
    cmp al, 0x21; je do_IS_NUM
    cmp al, 0x22; je do_IS_STR
    cmp al, 0x23; je do_IS_LIST
    cmp al, 0x09; je do_JMP
    cmp al, 0x0A; je do_JZ
    cmp al, 0x33; je do_JMP32
    cmp al, 0x0C; je do_CALL
    cmp al, 0x0D; je do_RET
    cmp al, 0x30; je do_WRBIN
    jmp dispatch           ; 未知 opcode → NOP

.halt:
    mov byte [rel halted], 1
.done:
    ret

; ═══════════════════════════════════════════════════════════
; 栈辅助 (内联于各 handler 中)
; push: mov [r13+r8*8], rx; inc r8
; pop:  dec r8; mov rx, [r13+r8*8]
; ═══════════════════════════════════════════════════════════

; ── PUSH I (0x01): 4B signed LE → tagged int ──
do_PUSH_I:
    movsxd rax, dword [r10 + r9]
    add r9, 4
    lea rax, [rax*2 + 1]
    mov [r13 + r8*8], rax
    inc r8
    jmp dispatch

; ── PUSH STR (0x2D): 1B len + len*2B UTF-16LE → tagged Str* ──
do_PUSH_STR:
    movzx ecx, byte [r10 + r9]
    inc r9
    push r9                 ; 入栈保护
    push rcx
    ; 算 UTF-8 长度
    lea rsi, [r10 + r9]
    mov edx, ecx
    xor edi, edi            ; utf8_len
.calc_len:
    test edx, edx; jz .calc_done
    movzx eax, word [rsi]
    add rsi, 2; dec edx
    cmp eax, 0x80; jb .c1
    cmp eax, 0x800; jb .c2
    add edi, 3; jmp .calc_len
.c2: add edi, 2; jmp .calc_len
.c1: inc edi; jmp .calc_len
.calc_done:
    ; 分配: edi + 8 字节
    push rdi
    lea edi, [edi + 8]
    call halloc
    pop rcx
    pop rdx                 ; char_count
    pop rsi                 ; 恢复 pc (实际未用)
    ; 填入头部
    mov dword [rax], 1      ; T_STR
    mov [rax + 4], ecx       ; len (utf8 bytes)
    ; 填入 UTF-8 数据
    lea rdi, [rax + 8]
    lea rsi, [r10 + r9]
    add r9, rdx
    add r9, rdx             ; pc += char_count * 2
    ; 复用 rdx = char_count
    mov ecx, edx
.str_loop:
    test ecx, ecx; jz .str_done
    movzx eax, word [rsi]
    add rsi, 2; dec ecx
    cmp eax, 0x80; jb .s1
    cmp eax, 0x800; jb .s2
    mov [rdi], al; shr eax, 8; or byte [rdi], 0xE0; inc rdi
    mov [rdi], al; and byte [rdi], 0x3F; or byte [rdi], 0x80; inc rdi
    mov [rdi], al; and byte [rdi], 0x3F; or byte [rdi], 0x80; inc rdi
    jmp .str_loop
.s2:
    mov [rdi], ah; or byte [rdi], 0xC0; inc rdi
    mov [rdi], al; and byte [rdi], 0x3F; or byte [rdi], 0x80; inc rdi
    jmp .str_loop
.s1:
    mov [rdi], al; inc rdi
    jmp .str_loop
.str_done:
    mov [r13 + r8*8], rax; inc r8
    jmp dispatch

; ── LOAD (0x07) / STORE (0x08) ──
do_LOAD:
    movzx eax, byte [r10 + r9]; inc r9
    mov rax, [r12 + rax*8]
    mov [r13 + r8*8], rax; inc r8
    jmp dispatch
do_STORE:
    movzx eax, byte [r10 + r9]; inc r9
    dec r8; mov rbx, [r13 + r8*8]
    mov [r12 + rax*8], rbx
    jmp dispatch

; ── 算术 (0x02-0x06) — 二元: 弹 b→a, 计算, 推结果 ──
do_ADD: dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rax,1; sar rbx,1; add rax,rbx; lea rax,[rax*2+1]; mov [r13+r8*8],rax; inc r8; jmp dispatch
do_SUB: dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rax,1; sar rbx,1; sub rbx,rax; lea rbx,[rbx*2+1]; mov [r13+r8*8],rbx; inc r8; jmp dispatch
do_MUL: dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rax,1; sar rbx,1; imul rbx,rax; lea rbx,[rbx*2+1]; mov [r13+r8*8],rbx; inc r8; jmp dispatch
do_DIV: dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rax,1; test rax,rax; jz .div_z; sar rbx,1; cqo; idiv rax; jmp .div_p
.div_z: xor rbx,rbx
.div_p: lea rbx,[rbx*2+1]; mov [r13+r8*8],rbx; inc r8; jmp dispatch
do_MOD: dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rax,1; test rax,rax; jz .mod_z; sar rbx,1; cqo; idiv rax; mov rbx,rdx; jmp .mod_p
.mod_z: xor rbx,rbx
.mod_p: lea rbx,[rbx*2+1]; mov [r13+r8*8],rbx; inc r8; jmp dispatch

; ── 比较 (0x13-0x17): 1=真, -1=假 ──
do_GT:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]
    sar rax,1; sar rbx,1; cmp rbx, rax
    setg al; movzx eax,al; lea rax,[rax*2-1]
    mov [r13+r8*8],rax; inc r8; jmp dispatch
do_LT:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]
    sar rax,1; sar rbx,1; cmp rbx, rax
    setl al; movzx eax,al; lea rax,[rax*2-1]
    mov [r13+r8*8],rax; inc r8; jmp dispatch
do_EQ:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]
    sar rax,1; sar rbx,1; cmp rbx, rax
    sete al; movzx eax,al; lea rax,[rax*2-1]
    mov [r13+r8*8],rax; inc r8; jmp dispatch
do_GTE:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]
    sar rax,1; sar rbx,1; cmp rbx, rax
    setge al; movzx eax,al; lea rax,[rax*2-1]
    mov [r13+r8*8],rax; inc r8; jmp dispatch

; ── IS_NUM / IS_STR / IS_LIST ──
do_IS_NUM:
    dec r8; mov rax,[r13+r8*8]; test al,1; setnz al
    movzx eax,al; lea rax,[rax*2-1]; mov [r13+r8*8],rax; inc r8; jmp dispatch
do_IS_STR:
    dec r8; mov rax,[r13+r8*8]; test al,1; jnz .is_str_f
    cmp dword [rax],1; sete al; jmp .is_str_p
.is_str_f: xor eax,eax
.is_str_p: movzx eax,al; lea rax,[rax*2-1]; mov [r13+r8*8],rax; inc r8; jmp dispatch
do_IS_LIST:
    dec r8; mov rax,[r13+r8*8]; test al,1; jnz .is_list_f
    cmp dword [rax],2; sete al; jmp .is_list_p
.is_list_f: xor eax,eax
.is_list_p: movzx eax,al; lea rax,[rax*2-1]; mov [r13+r8*8],rax; inc r8; jmp dispatch

; ── JMP (0x09): 2B signed offset ──
do_JMP:
    movsx eax, word [r10 + r9]; add r9, 2; add r9, rax; jmp dispatch
; ── JZ (0x0A): 弹栈, =0 则跳 ──
do_JZ:
    movsx eax, word [r10 + r9]; add r9, 2
    dec r8; mov rbx, [r13+r8*8]; sar rbx, 1
    test rbx, rbx; jnz dispatch; add r9, rax; jmp dispatch
; ── JMP32 (0x33): 4B signed offset ──
do_JMP32:
    movsxd rax, dword [r10 + r9]; add r9, 4; add r9, rax; jmp dispatch

; ── CALL (0x0C): 2B addr, 扫描 STORE 数 arg ──
do_CALL:
    movzx eax, word [r10 + r9]; add r9, 2
    test eax, eax; jz dispatch
    ; 参数计数: 扫描 entry 处的连续 STORE
    mov ecx, eax
    xor edx, edx
.cn: cmp byte [r10 + rcx], 0x08; jne .cd
    inc edx; add ecx, 2; jmp .cn
.cd:
    ; 保存帧: [ret_pc, sp, vars_ptr(未用)]
    mov [r15 + r14*8], r9    ; ret_pc
    inc r14
    ; sp -= arg_count (args 留在栈上用于 STORE 消费)
    ; 实际上标准做法: caller_base = sp - arg_count, 函数内 STORE 弹 args
    ; 简化: 不调整 sp，函数内 STORE 消费
    mov r9, rax             ; pc = addr
    jmp dispatch

; ── RET (0x0D) ──
do_RET:
    test r14, r14; jz .halt_vm
    dec r14
    mov r9, [r15 + r14*8]   ; 恢复 pc
    jmp dispatch
.halt_vm:
    mov byte [rel halted], 1
    jmp dispatch

; ── 列表 (0x27/25/2A/26/28/29) ──
do_LIST_NEW:
    dec r8; mov rax,[r13+r8*8]; sar rax,1  ; n = untag
    mov ecx, eax
    ; 分配: 16 + n*8
    lea edi, [ecx*8 + 16]; call halloc
    mov dword [rax], 2       ; T_LIST
    mov [rax+4], ecx; mov [rax+8], ecx
    ; 逆序填: items[n-1-i] = pop()
    mov edx, ecx
.ln_fill:
    test edx, edx; jz .ln_done
    dec r8; dec edx
    mov rbx, [r13+r8*8]
    mov [rax + 16 + rdx*8], rbx
    jmp .ln_fill
.ln_done:
    mov [r13+r8*8], rax; inc r8; jmp dispatch

do_LIST_GET:
    dec r8; mov rax,[r13+r8*8]; sar rax,1  ; idx (untag)
    dec r8; mov rbx,[r13+r8*8]             ; list*
    cmp eax, [rbx+4]; jae .lg_z
    mov rax, [rbx + 16 + rax*8]; jmp .lg_d
.lg_z: xor eax, eax
.lg_d: mov [r13+r8*8], rax; inc r8; jmp dispatch

do_LIST_LEN:
    dec r8; mov rax,[r13+r8*8]; mov eax,[rax+4]; lea rax,[rax*2+1]; mov [r13+r8*8],rax; inc r8; jmp dispatch

do_SET_ELEM:
    dec r8; mov rax,[r13+r8*8]   ; val
    dec r8; mov rbx,[r13+r8*8]; sar rbx,1  ; idx (untag)
    dec r8; mov rcx,[r13+r8*8]   ; list*
    cmp ebx, [rcx+4]; jae .se_d
    mov [rcx + 16 + rbx*8], rax
.se_d: jmp dispatch

do_LIST_CAT:
    ; TODO: 简化为 do_LIST_NEW 占位
    jmp dispatch

do_SLICE:
    jmp dispatch

; ── 字典 (stubs: 1D/1E/1F/20/32) ──
do_DICT:  jmp dispatch
do_DICT_GET: jmp dispatch
do_DICT_SET: jmp dispatch
do_DICT_HAS: jmp dispatch
do_DICT_KEYS: jmp dispatch

; ── 字符串 ops (stubs: 19/1A/1B/1C/31) ──
do_CONCAT: jmp dispatch
do_STRLEN: jmp dispatch
do_STRSUB: jmp dispatch
do_STREQ: jmp dispatch
do_ORD:   jmp dispatch

; ── WRITE_BINARY (0x30): stub ──
do_WRBIN: jmp dispatch

; ═══════════════════════════════════════════════════════════
; 堆分配 — bump allocator via brk(2)
;   input: edi = 字节数 (已对齐)
;   output: rax = 地址
; ═══════════════════════════════════════════════════════════
halloc:
    cmp qword [rel heap_ptr], 0
    jne .bump
    ; brk(0)
    mov eax, 12; xor edi, edi; syscall
    mov [rel heap_ptr], rax
    ; brk(cur + 256K)
    mov edi, eax; add edi, 0x40000; mov eax, 12; syscall
    mov [rel heap_end], rax
.bump:
    mov rax, [rel heap_ptr]
    add edi, 7; and edi, -8    ; 对齐
    add [rel heap_ptr], rdi
    cmp [rel heap_ptr], rax    ; 与 heap_end 比较 (通过 rax)
    jb .ok
    mov eax, 60; mov edi, 1; syscall  ; exit(1)
.ok:
    cmp [rel heap_ptr], [rel heap_end]
    ret

; ═══════════════════════════════════════════════════════════
; load_bin — 从文件加载 .bin
;   rdi = 路径
;   returns: eax = 0 (OK) or -1 (error)
;   加载到全局 code_buf / code_len
; ═══════════════════════════════════════════════════════════
load_bin:
    ; open(path, O_RDONLY)
    mov eax, 2; xor esi, esi; xor edx, edx; syscall
    test eax, eax; js .lb_fail
    mov ebx, eax             ; fd

    ; read 头部 10 字节到 tmp_buf
    mov edi, ebx; lea rsi, [rel tmp_buf]; mov edx, 10; mov eax, 0; syscall
    cmp eax, 10; jne .lb_close

    ; 验证 SAN0
    cmp dword [rel tmp_buf], 0x304E4153; jne .lb_close

    ; 清零变量
    movzx ecx, byte [rel tmp_buf + 5]
.xor_vars:
    test ecx, ecx; jz .vars_done
    dec ecx; mov qword [r12+rcx*8], 0; jmp .xor_vars
.vars_done:

    ; 代码大小 → code_len
    mov eax, [rel tmp_buf + 6]; mov [rel code_len], eax

    ; 读代码
    mov edi, ebx; lea rsi, [rel code_buf]; mov edx, eax; mov eax, 0; syscall
    mov edi, ebx; mov eax, 3; syscall  ; close
    xor eax, eax; ret

.lb_close:
    mov edi, ebx; mov eax, 3; syscall
.lb_fail:
    mov eax, -1; ret

; ═══════════════════════════════════════════════════════════
; BSS — 未初始化数据（紧跟代码段末，ELF 加载时 zero-fill）
; ═══════════════════════════════════════════════════════════
file_end:

align 8
stack:    resq 512     ; 操作数栈 (4KB)
vars:     resq 64      ; 变量数组 (512B)
cstk:     resq 64      ; 调用栈 (512B)
code_buf: resb 65536   ; 字节码缓冲 (64KB)
tmp_buf:  resb 16      ; load_bin 临时缓冲
code_len: resd 1
halted:   resb 1
heap_ptr: resq 1
heap_end: resq 1

mem_end:
