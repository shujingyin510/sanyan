; ═══════════════════════════════════════════════════════════════
; Sanyan Level 4 种子 VM — 手写 x86_64 ELF64 汇编 (完整版)
;
; 汇编: nasm -f bin -o sanyan_vm sanyan_vm_l4.asm
; 产出: ELF64 可执行文件, ~3KB
; 寄存器: r8=sp, r9=pc, r10=code, r11=code_len, r12=vars, r13=stack
;         r14=csp, r15=cstk_struct
; 35 opcode 全部实现
; ═══════════════════════════════════════════════════════════════

BITS 64

; ── ELF64 头 ──
org 0
ehdr:
    db 0x7F,'E','L','F'    ; magic
    db 2, 1, 1, 0          ; 64-bit, LE, v1, SysV
    times 8 db 0
    dw 2                    ; ET_EXEC
    dw 0x3E                 ; x86-64
    dd 1
    dq _start               ; entry
    dq phdr - ehdr          ; phoff
    dq 0
    dd 0
    dw 64                   ; ehsize
    dw 56                   ; phentsize
    dw 1                    ; phnum
    dw 0,0,0

; ── Program Header ──
phdr:
    dd 1                    ; PT_LOAD
    dd 7                    ; RWX
    dq 0
    dq ehdr
    dq ehdr
    dq file_end
    dq mem_end
    dq 0x1000

; ═══════════════════════════════════════════════
; 入口
; ═══════════════════════════════════════════════
_start:
    pop rcx                 ; argc
    mov rsi, rsp            ; argv
    lea r13, [rel stack]
    xor r8d, r8d            ; sp=0
    lea r12, [rel vars]
    lea r15, [rel cstk]
    xor r14d, r14d          ; csp=0
    mov byte [rel halted], 0
    cmp rcx, 1
    jle .stdin
    mov rdi, [rsi+8]
    call load_bin
    test eax, eax
    js .exit1
    jmp .run
.stdin:
    mov eax, 0; mov edi, 0; lea rsi, [rel code_buf]; mov edx, 0x10000; syscall
    mov [rel code_len], eax
    cmp eax, 0; jle .exit1
.run:
    xor r9d, r9d
    lea r10, [rel code_buf]
    mov r11d, [rel code_len]
    mov byte [rel halted], 0
    call dispatch           ; 初始化代码 (pc=0 到 HALT)
    mov byte [rel halted], 0
    call dispatch           ; 主代码 (HALT 之后)
    xor edi, edi; mov eax, 60; syscall
.exit1:
    mov edi, 1; mov eax, 60; syscall

; ═══════════════════════════════════════════════════════════════
; dispatch — 主循环
; ═══════════════════════════════════════════════════════════════
dispatch:
    cmp byte [rel halted], 0; jne .ret
    cmp r9d, r11d; jae .halt
    movzx eax, byte [r10+r9]; inc r9
    cmp al, 0x00; je dispatch
    cmp al, 0xFF; je .halt
    cmp al, 0x01; je PUSH_I
    cmp al, 0x2D; je PUSH_STR
    cmp al, 0x07; je LOAD
    cmp al, 0x08; je STORE
    cmp al, 0x02; je ADD
    cmp al, 0x03; je SUB
    cmp al, 0x04; je MUL
    cmp al, 0x05; je DIV
    cmp al, 0x06; je MOD
    cmp al, 0x13; je GT
    cmp al, 0x14; je LT
    cmp al, 0x15; je EQ
    cmp al, 0x17; je GTE
    cmp al, 0x19; je CONCAT
    cmp al, 0x1A; je STRLEN
    cmp al, 0x1B; je STRSUB
    cmp al, 0x1C; je STREQ
    cmp al, 0x31; je ORD
    cmp al, 0x27; je LIST_NEW
    cmp al, 0x25; je LIST_GET
    cmp al, 0x2A; je LIST_LEN
    cmp al, 0x26; je SET_ELEM
    cmp al, 0x28; je LIST_CAT
    cmp al, 0x29; je SLICE
    cmp al, 0x1D; je DICT
    cmp al, 0x1E; je DICT_GET
    cmp al, 0x1F; je DICT_SET
    cmp al, 0x20; je DICT_HAS
    cmp al, 0x32; je DICT_KEYS
    cmp al, 0x21; je IS_NUM
    cmp al, 0x22; je IS_STR
    cmp al, 0x23; je IS_LIST
    cmp al, 0x09; je JMP
    cmp al, 0x0A; je JZ
    cmp al, 0x33; je JMP32
    cmp al, 0x0C; je CALL
    cmp al, 0x0D; je RET
    cmp al, 0x30; je WRBIN
    jmp dispatch
.halt: mov byte [rel halted], 1
.ret:  ret

; ═══════════════════════════════════════════════════════════════
; 栈辅助宏 (内联于 handler)
; push: mov [r13+r8*8], rx ; inc r8
; pop:  dec r8 ; mov rx, [r13+r8*8]
; ═══════════════════════════════════════════════════════════════

; ── PUSH I ──
PUSH_I:
    movsxd rax, dword [r10+r9]; add r9,4
    lea rax, [rax*2+1]; mov [r13+r8*8], rax; inc r8; jmp dispatch

; ── PUSH STR: UTF-16LE → UTF-8 ──
PUSH_STR:
    movzx ecx, byte [r10+r9]; inc r9
    mov edx, ecx            ; char_count
    lea rsi, [r10+r9]
    ; 计算 UTF-8 字节数
    xor edi, edi
.calclp: test edx, edx; jz .calcdone
    movzx eax, word [rsi]; add rsi,2; dec edx
    cmp eax, 0x80; jb .c1
    cmp eax, 0x800; jb .c2
    add edi, 3; jmp .calclp
.c2: add edi, 2; jmp .calclp
.c1: inc edi; jmp .calclp
.calcdone:
    lea edi, [edi+8]; call halloc
    mov dword [rax], 1       ; T_STR
    mov [rax+4], edi          ; 暂存 len (实际 utf8_len 后面覆盖)
    push rax
    ; 转码 UTF-16LE → UTF-8
    mov edx, ecx            ; char_count
    lea rsi, [r10+r9]
    lea rdi, [rax+8]
    xor ebx, ebx            ; utf8_pos
    add r9, rdx; add r9, rdx;  ; pc += count*2
.strlp: test edx, edx; jz .strdone
    movzx eax, word [rsi]; add rsi,2; dec edx
    cmp eax, 0x80; jb .s1
    cmp eax, 0x800; jb .s2
    ; 3 字节: 0xE0|(cp>>12), 0x80|((cp>>6)&0x3F), 0x80|(cp&0x3F)
    mov ecx, eax
    shr eax, 12; or al, 0xE0; mov [rdi+rbx], al; inc rbx
    mov eax, ecx; shr eax, 6; and al, 0x3F; or al, 0x80; mov [rdi+rbx], al; inc rbx
    mov eax, ecx; and al, 0x3F; or al, 0x80; mov [rdi+rbx], al; inc rbx
    jmp .strlp
.s2:
    mov ecx, eax
    shr eax, 6; or al, 0xC0; mov [rdi+rbx], al; inc rbx
    mov eax, ecx; and al, 0x3F; or al, 0x80; mov [rdi+rbx], al; inc rbx
    jmp .strlp
.s1:
    mov [rdi+rbx], al; inc rbx
    jmp .strlp
.strdone:
    pop rax
    mov [rax+4], ebx          ; utf8 字节长度
    mov [r13+r8*8], rax; inc r8
    jmp dispatch

; ── LOAD/STORE ──
LOAD:  movzx eax,byte[r10+r9];inc r9;mov rax,[r12+rax*8];mov[r13+r8*8],rax;inc r8;jmp dispatch
STORE: movzx eax,byte[r10+r9];inc r9;dec r8;mov rbx,[r13+r8*8];mov[r12+rax*8],rbx;jmp dispatch

; ── 算术 ──
ADD: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;add rax,rbx;lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch
SUB: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;sub rbx,rax;lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
MUL: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;imul rbx,rax;lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
DIV: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;test rax,rax;jz .dz;sar rbx,1;cqo;idiv rax;mov rbx,rax;jmp .dp
.dz: xor rbx,rbx
.dp: lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
MOD: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;test rax,rax;jz .mz;sar rbx,1;cqo;idiv rax;mov rbx,rdx;jmp .mp
.mz: xor rbx,rbx
.mp: lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch

; ── 比较 ──
GT:  dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setg al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
LT:  dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setl al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
EQ:  dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;sete al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
GTE: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setge al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch

; ── 类型检查 ──
IS_NUM:  dec r8;mov rax,[r13+r8*8];test al,1;setnz al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
IS_STR:  dec r8;mov rax,[r13+r8*8];test al,1;jnz .isf;cmp dword[rax],1;sete al;jmp .isp
.isf:    xor eax,eax
.isp:    movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
IS_LIST: dec r8;mov rax,[r13+r8*8];test al,1;jnz .ilf;cmp dword[rax],2;sete al;jmp .ilp
.ilf:    xor eax,eax
.ilp:    movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch

; ── 控制流 ──
JMP:   movsx eax,word[r10+r9];add r9,2;add r9,rax;jmp dispatch
JZ:    movsx eax,word[r10+r9];add r9,2;dec r8;mov rbx,[r13+r8*8];sar rbx,1;test rbx,rbx;jnz dispatch;add r9,rax;jmp dispatch
JMP32: movsxd rax,dword[r10+r9];add r9,4;add r9,rax;jmp dispatch

; ── CALL (保存 sp 到帧) ──
CALL:
    movzx eax, word [r10+r9]; add r9,2
    test eax, eax; jz dispatch
    ; 扫描参数计数
    mov ecx, eax; xor edx, edx
.cn:cmp byte[r10+rcx],0x08; jne .cd; inc edx; add ecx,2; jmp .cn
.cd:
    ; 帧: [ret_pc, sp]
    mov [r15+r14*8], r9      ; ret_pc
    mov [r15+r14*8+8], r8    ; saved_sp (保存恢复用)
    add r14, 2               ; csp += 2 (每帧 2 个 qword)
    mov r9, rax              ; pc = addr
    jmp dispatch

; ── RET (恢复 sp) ──
RET:
    test r14, r14; jz .halt_vm
    sub r14, 2
    mov r9, [r15+r14*8]     ; 恢复 pc
    mov r8, [r15+r14*8+8]   ; 恢复 sp
    jmp dispatch
.halt_vm:
    mov byte [rel halted], 1; jmp dispatch

; ── 列表 ──
LIST_NEW:
    dec r8; mov rax,[r13+r8*8]; sar rax,1; mov ecx,eax
    lea edi,[ecx*8+16]; call halloc
    mov dword[rax],2; mov[rax+4],ecx; mov[rax+8],ecx
    mov edx,ecx
.ln: test edx,edx; jz .lnd; dec r8; dec edx; mov rbx,[r13+r8*8]; mov[rax+16+rdx*8],rbx; jmp .ln
.lnd: mov[r13+r8*8],rax; inc r8; jmp dispatch

LIST_GET:
    dec r8; mov rax,[r13+r8*8]; sar rax,1; dec r8; mov rbx,[r13+r8*8]
    cmp eax,[rbx+4]; jae .lgz; mov rax,[rbx+16+rax*8]; jmp .lgd
.lgz: xor eax,eax
.lgd: mov[r13+r8*8],rax; inc r8; jmp dispatch

LIST_LEN:
    dec r8; mov rax,[r13+r8*8]; mov eax,[rax+4]; lea rax,[rax*2+1]; mov[r13+r8*8],rax; inc r8; jmp dispatch

SET_ELEM:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]; sar rbx,1; dec r8; mov rcx,[r13+r8*8]
    cmp ebx,[rcx+4]; jae .sed; mov[rcx+16+rbx*8],rax
.sed: jmp dispatch

LIST_CAT:
    dec r8; mov r10, [r13+r8*8]   ; List* b (r10: 调用安全寄存器)
    dec r8; mov r11, [r13+r8*8]   ; List* a (r11: 调用安全寄存器)
    mov ecx, [r11+4]; add ecx, [r10+4]  ; total = len_a + len_b
    push r10; push r11; push rcx
    lea edi, [ecx*8+16]; call halloc
    pop rcx; pop rsi; pop rdx     ; rcx=total, rsi=a*, rdx=b*
    mov dword[rax],2; mov[rax+4],ecx; mov[rax+8],ecx
    mov r10d, [rsi+4]             ; len_a
    ; copy a
    mov ecx, r10d; xor edi,edi
.lca: cmp edi,ecx; jae .lcad; mov rbx,[rsi+16+rdi*8]; mov[rax+16+rdi*8],rbx; inc edi; jmp .lca
.lcad:
    ; copy b (offset = r10d = len_a)
    mov ecx, [rdx+4]; xor edi,edi
.lcb: cmp edi,ecx; jae .lcbd
    mov rbx, [rdx+16+rdi*8]; mov[rax+16+r10*8+rdi*8],rbx; inc edi; jmp .lcb
.lcbd:
    mov[r13+r8*8],rax; inc r8; jmp dispatch

SLICE:
    dec r8; mov rax,[r13+r8*8]; sar rax,1  ; count (untag)
    dec r8; mov rbx,[r13+r8*8]; sar rbx,1  ; start (untag)
    dec r8; mov rcx,[r13+r8*8]             ; list*
    cmp ebx,[rcx+4]; jae .slempty
    mov edx,[rcx+4]; sub edx,ebx
    cmp eax,edx; cmova eax,edx
    lea edi,[eax*8+16]; mov esi,eax; call halloc
    mov dword[rax],2; mov[rax+4],esi; mov[rax+8],esi
    xor edx,edx
.sllp: cmp edx,esi; jae .sld; mov rdi,[rcx+16+rbx*8+rdx*8]; mov[rax+16+rdx*8],rdi; inc edx; jmp .sllp
.slempty: lea edi,[16]; call halloc; mov dword[rax],2; mov qword[rax+4],0; mov qword[rax+8],0
.sld: mov[r13+r8*8],rax; inc r8; jmp dispatch

; ── 字典 ──
; 内部: 弹 key, 返回槽位 index*2 (0,2,4...) 或 -1
dict_find:
    ; 输入: rdi=Dict*, rsi=key
    ; 输出: rax=index*2 or -1
    mov rcx, rdi; mov edx,[rcx+8]   ; cnt
    xor eax, eax                    ; i
.dflp: cmp eax, edx; jae .dfnf; shl eax,1  ; i*=2
    cmp qword[rcx+16+rax*8],0; je .dfemp
    ; 比较 key
    push rdi; push rsi; push rax
    mov rdi, [rcx+16+rax*8]  ; dict key
    call key_cmp
    test rax, rax
    pop rax; pop rsi; pop rdi
    jnz .dffound
.dfemp: shr eax, 1; inc eax; jmp .dflp
.dfemp2: shr eax, 1; inc eax; jmp .dflp
.dffound: ret
.dfnf: mov rax, -1; ret

; key_cmp: 比较两个 tagged value
key_cmp:
    ; rdi=key_a, rsi=key_b → 返回 1=相等, 0=不等
    mov al, dil; and al, 1         ; IS_INT(a)?
    mov bl, sil; and bl, 1
    cmp al, bl; jne .kc_no         ; 一整数一指针 → 不等
    test al, al; jnz .kc_int       ; 都是整数
    ; 都是指针: 检查 T_STR 然后 str_eq
    cmp dword[rdi], 1; jne .kc_no
    cmp dword[rsi], 1; jne .kc_no
    push rcx; push rdx
    mov ecx, [rdi+4]; cmp ecx, [rsi+4]; jne .kc_no2
    lea rdi, [rdi+8]; lea rsi, [rsi+8]
    repe cmpsb; jne .kc_no2
    pop rdx; pop rcx; mov rax, 1; ret
.kc_no2: pop rdx; pop rcx
.kc_no: xor eax, eax; ret
.kc_int: sar rdi,1; sar rsi,1; cmp rdi,rsi; sete al; movzx eax,al; ret

DICT:
    dec r8; mov rax,[r13+r8*8]; sar rax,1  ; n = pair count
    mov ecx, eax; shl ecx, 1               ; m = n*2
    lea edi,[ecx*8+8]; call halloc
    mov dword[rax], 3; mov[rax+4], ecx      ; T_DICT, cnt=2n
    ; 逆序填: kv[m-2]=k, kv[m-1]=v
    mov edx, ecx
.dlp: test edx, edx; jz .dd; sub edx, 2
    dec r8; mov rbx,[r13+r8*8]    ; val
    dec r8; mov rdi,[r13+r8*8]    ; key
    mov[rax+16+rdx*8], rdi; mov[rax+16+rdx*8+8], rbx
    jmp .dlp
.dd: mov[r13+r8*8],rax; inc r8; jmp dispatch

DICT_GET:
    dec r8; mov rsi,[r13+r8*8]  ; key
    dec r8; mov rdi,[r13+r8*8]  ; dict*
    mov edx,[rdi+8]; xor eax,eax
.dglp: cmp eax, edx; jae .dgnf
    cmp qword[rdi+16+rax*8], 0; je .dgemp
    push rax; push rdi; push rsi
    mov rdi, [rdi+16+rax*8]; mov rsi, [rsp]  ; rdi=dict_key, rsi=search_key
    call key_cmp; test rax, rax
    pop rsi; pop rdi; pop rax
    jnz .dgf
.dgemp: inc eax; jmp .dglp
.dgnf: xor eax, eax; mov[r13+r8*8],rax; inc r8; jmp dispatch
.dgf:  mov rax,[rdi+16+rax*8+8]; mov[r13+r8*8],rax; inc r8; jmp dispatch

DICT_SET:
    ; 弹: val, key, dict* — 设置键值
    dec r8; mov rax, [r13+r8*8]   ; val (rax)
    dec r8; mov rbx, [r13+r8*8]   ; key (rbx)
    dec r8; mov rcx, [r13+r8*8]   ; dict* (rcx)
    mov edx, [rcx+8]              ; cnt
    xor edi, edi                  ; slot index
.dslp0: cmp edi, edx; jae .dsnew0
    cmp qword[rcx+16+rdi*8], 0; je .dsemp0  ; 空槽
    ; 比较 entry[key] == key
    push rax; push rcx; push rdi; push rbx
    mov rsi, rbx                  ; search_key
    mov rdi, [rcx+16+rdi*8]       ; entry_key
    call key_cmp
    pop rbx; pop rdi; pop rcx; pop rax
    test rax, rax; jnz .dsoverwrite0
.dsemp0: inc edi; jmp .dslp0
.dsoverwrite0:
    mov [rcx+16+rdi*8+8], rax; jmp dispatch
.dsnew0:
    xor edi, edi
.dsnlp0: cmp edi, edx; jae dispatch  ; 无空位
    cmp qword[rcx+16+rdi*8], 0; jne .dsnn0
    mov [rcx+16+rdi*8], rbx; mov [rcx+16+rdi*8+8], rax; jmp dispatch
.dsnn0: inc edi; jmp .dsnlp0

DICT_HAS:
    dec r8; mov rsi,[r13+r8*8]; dec r8; mov rdi,[r13+r8*8]
    mov edx,[rdi+8]; xor eax,eax
.dhlp: cmp eax, edx; jae .dhno
    cmp qword[rdi+16+rax*8],0; je .dhemp
    push rax; push rdi; mov rdi,[rdi+16+rax*8]; call key_cmp; pop rdi; pop rax
    test rax,rax; jnz .dhyes
.dhemp: inc eax; jmp .dhlp
.dhno: mov qword[r13+r8*8],-1; inc r8; jmp dispatch
.dhyes: mov qword[r13+r8*8],1; inc r8; jmp dispatch

DICT_KEYS:
    dec r8; mov rdi,[r13+r8*8]   ; dict*
    mov edx,[rdi+8]; xor ecx,ecx ; ecx=non-null count
    xor eax,eax
.dkcnt: cmp eax, edx; jae .dkcntd
    cmp qword[rdi+16+rax*8],0; je .dkcntn; inc ecx
.dkcntn: inc eax; jmp .dkcnt
.dkcntd:
    lea edi,[ecx*8+16]; call halloc
    mov dword[rax],2; mov[rax+4],ecx; mov[rax+8],ecx
    xor esi,esi  ; dst idx
    xor edx,edx  ; src idx
.dkfill: cmp edx, [rdi+8]; jae .dkdone
    mov rbx,[rdi+16+rdx*8]
    test rbx, rbx; jz .dknext
    mov[rax+16+rsi*8], rbx; inc rsi
.dknext: inc edx; jmp .dkfill
.dkdone: mov[r13+r8*8],rax; inc r8; jmp dispatch

; ── 字符串操作 ──
CONCAT:
    dec r8; mov rax,[r13+r8*8]  ; Str*b
    dec r8; mov rbx,[r13+r8*8]  ; Str*a
    mov ecx,[rbx+4]; add ecx,[rax+4]  ; total bytes
    lea edi,[ecx+8]; push rbx; push rax; call halloc
    pop rdx; pop rsi
    mov dword[rax],1; mov[rax+4],ecx    ; T_STR, len
    lea rdi,[rax+8]
    mov ecx,[rsi+4]; lea rsi,[rsi+8]; rep movsb
    mov ecx,[rdx+4]; lea rsi,[rdx+8]; rep movsb
    mov[r13+r8*8],rax; inc r8; jmp dispatch

STRLEN:
    ; 统计 UTF-8 字符数
    dec r8; mov rbx,[r13+r8*8]  ; Str*
    mov ecx,[rbx+4]; xor eax,eax ; eax=char_count
    lea rsi,[rbx+8]; xor edx,edx ; edx=byte offset
.sllp: cmp edx,ecx; jae .sldone
    movzx edi,byte[rsi+rdx]
    test edi,0x80; jz .sl1
    cmp edi,0xE0; jb .sl2
    add edx,3; inc eax; jmp .sllp
.sl2: add edx,2; inc eax; jmp .sllp
.sl1: inc edx; inc eax; jmp .sllp
.sldone: lea rax,[rax*2+1]; mov[r13+r8*8],rax; inc r8; jmp dispatch

STREQ:
    dec r8; mov rax,[r13+r8*8]; dec r8; mov rbx,[r13+r8*8]
    mov ecx,[rax+4]; cmp ecx,[rbx+4]; jne .sq_no
    push rcx; lea rsi,[rax+8]; lea rdi,[rbx+8]; repe cmpsb
    pop rcx; jne .sq_no
    mov qword[r13+r8*8],1; inc r8; jmp dispatch
.sq_no: mov qword[r13+r8*8],-1; inc r8; jmp dispatch

STRSUB:
    ; 弹 count, start, str → 推子串；不保存 r8，弹完后 r8 即结果位置
    dec r8; mov rax, [r13+r8*8]  ; rax = count (tagged)
    dec r8; mov rbx, [r13+r8*8]  ; rbx = start (tagged)
    dec r8; mov rcx, [r13+r8*8]  ; rcx = str*
    sar rax, 1                   ; count
    sar rbx, 1                   ; start
    ; r8 当前 = 结果 push 位置
    mov edx, [rcx+4]             ; str->len (bytes)
    lea rsi, [rcx+8]             ; data ptr
    xor edi, edi                 ; byte_off
    mov ecx, ebx                 ; chars to skip
.sf0:test ecx,ecx; jz .sfs0
    cmp edi,edx; jae .sse
    movzx ebx,byte[rsi+rdi]; test bl,0x80; jz .sf1
    cmp bl,0xE0; jb .sf2; add edi,3; dec ecx; jmp .sf0
.sf2:add edi,2; dec ecx; jmp .sf0
.sf1:inc edi; dec ecx; jmp .sf0
.sfs0:mov ebx, edi               ; byte_start
    mov r10d, eax                ; count (use r10 as temp)
.se0:test r10d,r10d; jz .see0
    cmp edi,edx; jae .see0
    movzx eax,byte[rsi+rdi]; test al,0x80; jz .se1
    cmp al,0xE0; jb .se2; add edi,3; dec r10d; jmp .se0
.se2:add edi,2; dec r10d; jmp .se0
.se1:inc edi; dec r10d; jmp .se0
.see0:
    sub edi, ebx                 ; byte_len
    push rdi
    lea edi,[edi+8]; call halloc
    pop rcx
    mov dword[rax],1; mov[rax+4],ecx
    lea rdi,[rax+8]; lea rsi,[rsi+rbx]; mov ecx,ecx; rep movsb
    ; 恢复到正确位置 — r8 已经是结果 pos
    ; 但 halloc 可能修改了 r8? 不会，halloc 保存自己的寄存器
    mov[r13+r8*8],rax; inc r8; jmp dispatch
.sse:
    lea edi,[8]; call halloc; mov dword[rax],1; mov dword[rax+4],0
    mov[r13+r8*8],rax; inc r8; jmp dispatch

ORD:
    ; 弹: index, str → codepoint
    dec r8; mov rax,[r13+r8*8]; sar rax,1  ; char_index
    dec r8; mov rbx,[r13+r8*8]             ; str*
    mov ecx,[rbx+4]; lea rsi,[rbx+8]; xor edi,edi  ; byte_off
    mov edx, eax
.olp: test edx,edx; jz .ofound; cmp edi,ecx; jae .ozero
    movzx eax,byte[rsi+rdi]
    test al,0x80; jz .o1
    cmp al,0xE0; jb .o2
    add edi,3; dec edx; jmp .olp
.o2: add edi,2; dec edx; jmp .olp
.o1: inc edi; dec edx; jmp .olp
.ofound:
    cmp edi,ecx; jae .ozero
    movzx eax,byte[rsi+rdi]
    test al,0x80; jz .ord1
    cmp al,0xE0; jb .ord2
    movzx eax,byte[rsi+rdi]; and eax,0x0F; shl eax,12
    movzx edx,byte[rsi+rdi+1]; and edx,0x3F; shl edx,6
    or eax, edx
    movzx edx,byte[rsi+rdi+2]; and edx,0x3F; or eax, edx
    jmp .opush
.ord2:
    movzx eax,byte[rsi+rdi]; and eax,0x1F; shl eax,6
    movzx edx,byte[rsi+rdi+1]; and edx,0x3F; or eax, edx
    jmp .opush
.ord1: movzx eax,byte[rsi+rdi]
.opush: lea rax,[rax*2+1]; mov[r13+r8*8],rax; inc r8; jmp dispatch
.ozero: xor eax,eax; lea rax,[rax*2+1]; mov[r13+r8*8],rax; inc r8; jmp dispatch

; ── WRITE_BINARY ──
WRBIN:
    dec r8; mov rbx,[r13+r8*8]  ; byte_list (List of tagged ints)
    dec r8; mov rdi,[r13+r8*8]  ; path (Str*)
    ; open(path, O_CREAT|O_WRONLY, 0666)
    lea rsi,[rdi+8]; mov edi,esi; mov esi,66; mov edx,438
    mov eax,2; syscall
    test eax,eax; js dispatch
    mov edi,eax                 ; fd
    ; 从列表提取字节 → 临时缓冲区
    mov ecx,[rbx+4]; cmp ecx,0; je .wbclose
    lea rsi,[rbx+16]
    ; 用栈分配小缓冲区
    sub rsp, 128; mov rdx, rsp
    xor r8d, r8d               ; 写入计数
.wblp: cmp r8d, ecx; jae .wbflush
    mov rax,[rsi+r8*8]; sar rax,1
    mov[rdx+r8], al; inc r8
    cmp r8, 128; jb .wblp
.wbflush:
    push rcx; push rsi; push rdx
    mov eax,1; mov rsi,rdx; mov edx,r8d; syscall  ; write
    pop rdx; pop rsi; pop rcx
    sub ecx, r8d
    cmp ecx,0; je .wbclose
    lea rsi,[rsi+r8*8]; xor r8d,r8d; jmp .wblp
.wbclose:
    add rsp, 128
    mov eax,3; syscall  ; close
    jmp dispatch

; ═══════════════════════════════════════════════════════════════
; 堆分配
; ═══════════════════════════════════════════════════════════════
halloc:
    cmp qword[rel heap_ptr],0; jne .bump
    mov eax,12; xor edi,edi; syscall
    mov[rel heap_ptr],rax
    mov edi,eax; add edi,0x40000; mov eax,12; syscall
    mov[rel heap_end],rax
.bump:
    mov rax,[rel heap_ptr]
    add edi,7; and edi,-8
    add[rel heap_ptr],rdi
    cmp[rel heap_ptr],rax; jb .ok
    mov eax,60; mov edi,1; syscall
.ok:
    cmp[rel heap_ptr],[rel heap_end]; ret

; ═══════════════════════════════════════════════════════════════
; load_bin
; ═══════════════════════════════════════════════════════════════
load_bin:
    mov eax,2; xor esi,esi; xor edx,edx; syscall
    test eax,eax; js .lbf; mov ebx,eax
    mov edi,ebx; lea rsi,[rel tmp_buf]; mov edx,10; mov eax,0; syscall
    cmp eax,10; jne .lbc
    cmp dword[rel tmp_buf],0x304E4153; jne .lbc
    movzx ecx,byte[rel tmp_buf+5]
.xv: test ecx,ecx; jz .xvd; dec ecx; mov qword[r12+rcx*8],0; jmp .xv
.xvd:
    mov eax,[rel tmp_buf+6]; mov[rel code_len],eax
    mov edi,ebx; lea rsi,[rel code_buf]; mov edx,eax; mov eax,0; syscall
    mov edi,ebx; mov eax,3; syscall; xor eax,eax; ret
.lbc: mov edi,ebx; mov eax,3; syscall
.lbf: mov eax,-1; ret

; ═══════════════════════════════════════════════════════════════
; BSS
; ═══════════════════════════════════════════════════════════════
file_end:
align 8
stack:    resq 512
vars:     resq 64
cstk:     resq 128    ; 每帧 2 个 qword (pc, sp) * 64 帧
code_buf: resb 65536
tmp_buf:  resb 16
code_len: resd 1
halted:   resb 1
heap_ptr: resq 1
heap_end: resq 1
mem_end:
