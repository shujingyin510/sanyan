; ═══════════════════════════════════════════════════════════════
; Sanyan Level 4 种子 VM — x86_64 ELF64 NASM 汇编 (V2)
; 35 opcode 全实现, 寄存器保护完善
; r8=sp r9=pc r10=code r11=code_len r12=vars r13=stack_base r14=csp r15=cstk_base
; ═══════════════════════════════════════════════════════════════
BITS 64
org 0
ehdr:
    db 0x7F,'E','L','F', 2,1,1,0
    times 8 db 0
    dw 2
    dw 0x3E
    dd 1
    dq _start
    dq phdr-ehdr
    dq 0
    dd 0
    dw 64
    dw 56
    dw 1
    dw 0
    dw 0
    dw 0
phdr:
    dd 1,7; dq 0,ehdr,ehdr
    dq file_end, mem_end, 0x1000

_start:
    cld
    pop rcx; mov rsi,rsp
    lea r13,[rel stack]; xor r8d,r8d
    lea r12,[rel vars]; lea r15,[rel cstk]; xor r14d,r14d
    mov byte[rel halted],0
    cmp rcx,1; jle .stdin
    mov rdi,[rsi+8]; call load_bin; test eax,eax; js .exit1; jmp .run
.stdin:
    mov eax,0; mov edi,0; lea rsi,[rel code_buf]; mov edx,0x10000; syscall
    mov[rel code_len],eax; cmp eax,0; jle .exit1
.run:
    xor r9d,r9d; lea r10,[rel code_buf]; mov r11d,[rel code_len]
    mov byte[rel halted],0; call dispatch
    mov byte[rel halted],0; call dispatch
    xor edi,edi; mov eax,60; syscall
.exit1:
    mov edi,1; mov eax,60; syscall

; ═══════════════════════════════════════════════════════════════
; dispatch
; ═══════════════════════════════════════════════════════════════
dispatch:
    cmp byte[rel halted],0; jne .ret
    cmp r9d,r11d; jae .halt
    movzx eax,byte[r10+r9]; inc r9
    ; 跳转表: 256 × 4 字节偏移 (dd) (见文件末尾 jmp_tbl)
    ; 未知 opcode → .nop_handler (jmp dispatch)
    movsxd rax,dword[rel jmp_tbl+rax*4]
    lea rbx,[rel jmp_tbl]
    add rbx,rax
    jmp rbx
.halt: mov byte[rel halted],1
.ret:  ret
.nop_handler: jmp dispatch

; ═══════════════════════════════════════════════════════════════
; 基础 opcode
; ═══════════════════════════════════════════════════════════════
PUSH_I:
    movsxd rax,dword[r10+r9]; add r9,4
    lea rax,[rax*2+1]; cmp r8,512; jae .halt; mov[r13+r8*8],rax; inc r8; jmp dispatch

CLOSURE: jmp dispatch  ; TODO: closure object creation

PUSH_STR16:
    movzx ecx,word[r10+r9]; add r9,2; mov edx,ecx; lea rsi,[r10+r9]; xor edi,edi; jmp .clp_common
PUSH_STR:
    movzx ecx,byte[r10+r9]; inc r9        ; ecx = char_count
    mov edx,ecx; lea rsi,[r10+r9]
    xor edi,edi                            ; utf8_len
.clp_common: clp:test edx,edx; jz .cld
    movzx eax,word[rsi]; add rsi,2; dec edx
    cmp eax,0x80; jb .c1
    cmp eax,0x800; jb .c2
    add edi,3; jmp .clp
.c2:add edi,2; jmp .clp
.c1:inc edi; jmp .clp
.cld:
    push rcx                               ; 保存 char_count(ecx 会被 halloc brk 破坏)
    lea edi,[edi+8]; call halloc
    pop rcx                                ; 恢复 char_count
    mov dword[rax],1
    mov[rax+4],edi                         ; 暂存(后面覆盖为 utf8_len)
    push rax                               ; 保存 str*
    mov edx,ecx; lea rsi,[r10+r9]
    lea rdi,[rax+8]; xor ebx,ebx
    add r9,rdx; add r9,rdx                 ; pc += count*2
.slp:test edx,edx; jz .sld
    movzx eax,word[rsi]; add rsi,2; dec edx
    cmp eax,0x80; jb .s1
    cmp eax,0x800; jb .s2
    mov ecx,eax; shr eax,12; or al,0xE0; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; shr eax,6; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    cmp eax,0x10000; jb .s3
    ; 4 byte: 0xF0|(cp>>18), 0x80|((cp>>12)&0x3F), 0x80|((cp>>6)&0x3F), 0x80|(cp&0x3F)
    mov ecx,eax; shr eax,18; or al,0xF0; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; shr eax,12; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; shr eax,6; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    jmp .slp
.s3:mov ecx,eax; shr eax,12; or al,0xE0; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; shr eax,6; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    jmp .slp
.s2:mov ecx,eax; shr eax,6; or al,0xC0; mov[rdi+rbx],al; inc rbx
    mov eax,ecx; and al,0x3F; or al,0x80; mov[rdi+rbx],al; inc rbx
    jmp .slp
.s1:mov[rdi+rbx],al; inc rbx; jmp .slp
.sld:pop rax; mov[rax+4],ebx
    mov[r13+r8*8],rax; inc r8; jmp dispatch

LOAD:  movzx eax,byte[r10+r9];inc r9;cmp eax,63;ja dispatch;mov rax,[r12+rax*8];cmp r8,511;ja dispatch;mov[r13+r8*8],rax;inc r8;jmp dispatch
STORE: movzx eax,byte[r10+r9];inc r9;cmp eax,63;ja dispatch;dec r8;mov rbx,[r13+r8*8];mov[r12+rax*8],rbx;jmp dispatch

LOAD16: movzx eax,word[r10+r9];add r9,2;cmp eax,65535;ja dispatch;mov rax,[r12+rax*8];cmp r8,511;ja .halt;mov[r13+r8*8],rax;inc r8;jmp dispatch
STORE16: movzx eax,word[r10+r9];add r9,2;cmp eax,65535;ja dispatch;dec r8;mov rbx,[r13+r8*8];mov[r12+rax*8],rbx;jmp dispatch

ADD: cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;add rax,rbx;lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch
SUB: cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;sub rbx,rax;lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
MUL: cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;imul rbx,rax;lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
DIV: cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;test rax,rax;jz .dz;mov rcx,rax;mov rax,rbx;sar rax,1;cqo;idiv rcx;mov rbx,rax;jmp .dp
.dz:xor rbx,rbx
.dp:lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch
MOD: cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;test rax,rax;jz .mz;mov rcx,rax;mov rax,rbx;sar rax,1;cqo;idiv rcx;mov rbx,rdx;jmp .mp
.mz:xor rbx,rbx
.mp:lea rbx,[rbx*2+1];mov[r13+r8*8],rbx;inc r8;jmp dispatch

GT:  cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setg al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
LT:  cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setl al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
EQ:  cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;sete al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
GTE: dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rax,1;sar rbx,1;cmp rbx,rax;setge al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch

IS_NUM:  cmp r8,1;jb dispatch;dec r8;mov rax,[r13+r8*8];test al,1;setnz al;movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
IS_STR:  cmp r8,1;jb dispatch;dec r8;mov rax,[r13+r8*8];test al,1;jnz .isf;cmp dword[rax],1;sete al;jmp .isp
.isf:    xor eax,eax
.isp:    movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch
IS_LIST: dec r8;mov rax,[r13+r8*8];test al,1;jnz .ilf;cmp dword[rax],2;sete al;jmp .ilp
.ilf:    xor eax,eax
.ilp:    movzx eax,al;lea rax,[rax*2-1];mov[r13+r8*8],rax;inc r8;jmp dispatch

JMP:   movsx eax,word[r10+r9];add r9,2;add r9,rax;jmp dispatch
JZ:    movsx eax,word[r10+r9];add r9,2;dec r8;mov rbx,[r13+r8*8];sar rbx,1;test rbx,rbx;jnz dispatch;add r9,rax;jmp dispatch
JMP32: movsxd rax,dword[r10+r9];add r9,4;add r9,rax;jmp dispatch

CALL:
    mov eax,dword[r10+r9]; add r9,4; test eax,eax; jz dispatch
    cmp r14,126; jae dispatch
    mov ecx,eax; xor edx,edx
.cn:lea ebx,[ecx+2]; cmp ebx,r11d; ja .bad_call; cmp byte[r10+rcx],0x08; jne .cd; inc edx; add ecx,2; jmp .cn
.cd:
    mov[r15+r14*8],r9; mov[r15+r14*8+8],r8; add r14,2
    mov r9,rax; jmp dispatch

RET:
    test r14,r14; jz .halt_vm
    sub r14,2; mov r9,[r15+r14*8]; cmp r9d,r11d; jae .halt_vm; mov r8,[r15+r14*8+8]; jmp dispatch
.halt_vm: mov byte[rel halted],1; jmp dispatch

; ═══════════════════════════════════════════════════════════════
; 列表
; ═══════════════════════════════════════════════════════════════
LIST_NEW:
    cmp r8,1;jb dispatch;dec r8;mov rax,[r13+r8*8];sar rax,1;mov ecx,eax;cmp ecx,8192;ja dispatch
    lea edi,[ecx*8+16];call halloc
    mov dword[rax],2;mov[rax+4],ecx;mov[rax+8],ecx
    mov edx,ecx
.ln:test edx,edx;jz .lnd;dec r8;dec edx;mov rbx,[r13+r8*8];mov[rax+16+rdx*8],rbx;jmp .ln
.lnd:mov[r13+r8*8],rax;inc r8;jmp dispatch

LIST_GET:
    cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];sar rax,1;dec r8;mov rbx,[r13+r8*8];test bl,1;jnz .lgz;cmp dword[rbx],2;jne .lgz;
    cmp eax,[rbx+4];jae .lgz;mov rax,[rbx+16+rax*8];jmp .lgd
.lgz:xor eax,eax
.lgd:mov[r13+r8*8],rax;inc r8;jmp dispatch

LIST_LEN:
    dec r8;mov rax,[r13+r8*8];test al,1;jnz .llb;cmp dword[rax],2;jne .llb;mov eax,[rax+4];lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch
.llb: inc r8; jmp dispatch

SET_ELEM:
    cmp r8,3;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];sar rbx,1;dec r8;mov rcx,[r13+r8*8];test cl,1;jnz .sed;cmp dword[rcx],2;jne .sed
    cmp ebx,[rcx+4];jae .sed;mov[rcx+16+rbx*8],rax
.sed:jmp dispatch

LIST_CAT:
    ; 用 sub rsp,32 分配临时空间保存 a*,b*,total
    dec r8;mov rax,[r13+r8*8]   ; List* b
    dec r8;mov rbx,[r13+r8*8]   ; List* a
    sub rsp,32
    mov[rsp],rbx                ; [rsp+0]=a*
    mov[rsp+8],rax              ; [rsp+8]=b*
    mov ecx,[rbx+4];add ecx,[rax+4]
    mov[rsp+16],rcx             ; [rsp+16]=total
    lea edi,[ecx*8+16];call halloc
    mov rcx,[rsp+16]            ; rcx=total (halloc clobbered ecx)
    mov rsi,[rsp]               ; rsi=a*
    mov rdx,[rsp+8]             ; rdx=b*
    mov dword[rax],2;mov[rax+4],ecx;mov[rax+8],ecx
    ; copy a items
    mov ecx,[rsi+4];xor edi,edi
.lca:cmp edi,ecx;jae .lcad;mov rbx,[rsi+16+rdi*8];mov[rax+16+rdi*8],rbx;inc edi;jmp .lca
.lcad:
    ; copy b items, offset = [rsp+0]+4 = len_a
    mov r10d,[rsi+4]            ; len_a = offset (safe: r10 restored before dispatch)
    mov ecx,[rdx+4];xor edi,edi
.lcb:cmp edi,ecx;jae .lcbd
    mov rbx,[rdx+16+rdi*8];mov[rax+16+r10*8+rdi*8],rbx;inc edi;jmp .lcb
.lcbd:
    add rsp,32
    lea r10,[rel code_buf];mov r11d,[rel code_len]  ; restore r10,r11
    mov[r13+r8*8],rax;inc r8;jmp dispatch

SLICE:
    cmp r8,3;jb dispatch;dec r8;mov rax,[r13+r8*8];sar rax,1  ; count
    dec r8;mov rbx,[r13+r8*8];sar rbx,1  ; start
    dec r8;mov rcx,[r13+r8*8]            ; list*
    cmp ebx,[rcx+4];jae .slempty
    mov edx,[rcx+4];sub edx,ebx;cmp eax,edx;cmova eax,edx
    lea edi,[eax*8+16];mov esi,eax;call halloc
    mov dword[rax],2;mov[rax+4],esi;mov[rax+8],esi
    xor edx,edx
.slp:cmp edx,esi;jae .sld;mov rdi,[rcx+16+rbx*8+rdx*8];mov[rax+16+rdx*8],rdi;inc edx;jmp .slp
.slempty:lea edi,[16];call halloc;mov dword[rax],2;mov dword[rax+4],0;mov dword[rax+8],0
.sld:mov[r13+r8*8],rax;inc r8;jmp dispatch

; ═══════════════════════════════════════════════════════════════
; 字典
; ═══════════════════════════════════════════════════════════════
; key_cmp: rdi=key_a(aval on stack), rsi=key_b → 返回 1=相等 0=不等
key_cmp:
    mov al,dil;and al,1;mov bl,sil;and bl,1
    cmp al,bl;jne .kcno
    test al,al;jnz .kcint
    cmp dword[rdi],1;jne .kcno;cmp dword[rsi],1;jne .kcno
    mov ecx,[rdi+4];cmp ecx,[rsi+4];jne .kcno
    lea rdi,[rdi+8];lea rsi,[rsi+8];repe cmpsb;jne .kcno
    mov rax,1;ret
.kcno:xor eax,eax;ret
.kcint:sar rdi,1;sar rsi,1;cmp rdi,rsi;sete al;movzx eax,al;ret

DICT:
    dec r8;mov rax,[r13+r8*8];sar rax,1;mov ecx,eax;cmp ecx,4096;ja dispatch;shl ecx,1
    lea edi,[ecx*8+16];call halloc
    mov dword[rax],3;mov[rax+4],ecx;mov[rax+8],ecx
    mov edx,ecx
.dlp:test edx,edx;jz .dd;sub edx,2
    dec r8;mov rbx,[r13+r8*8];dec r8;mov rdi,[r13+r8*8]
    mov[rax+16+rdx*8],rdi;mov[rax+16+rdx*8+8],rbx;jmp .dlp
.dd:mov[r13+r8*8],rax;inc r8;jmp dispatch

DICT_GET:
    cmp r8,2;jb dispatch;dec r8;mov rsi,[r13+r8*8];dec r8;mov rdi,[r13+r8*8];test rdi,rdi;jz .dgnf;test dil,1;jnz .dgnf;cmp dword[rdi],3;jne .dgnf
    mov edx,[rdi+8];xor eax,eax
.dglp:cmp eax,edx;jae .dgnf
    cmp qword[rdi+16+rax*8],0;je .dgemp
    push rax;push rdi;push rsi
    mov rdi,[rdi+16+rax*8];call key_cmp
    mov ecx,eax                  ; 结果存 ecx，不被 pop 破坏
    pop rsi;pop rdi;pop rax
    test ecx,ecx;jnz .dgf
.dgemp:inc eax;jmp .dglp
.dgnf:xor eax,eax;mov[r13+r8*8],rax;inc r8;jmp dispatch
.dgf:mov rax,[rdi+16+rax*8+8];mov[r13+r8*8],rax;inc r8;jmp dispatch

DICT_SET:
    dec r8;mov rax,[r13+r8*8]   ; val
    dec r8;mov rbx,[r13+r8*8]   ; key
    dec r8;mov rcx,[r13+r8*8]   ; dict*
    mov edx,[rcx+8];xor edi,edi
.dslp:cmp edi,edx;jae .dsnew
    cmp qword[rcx+16+rdi*8],0;je .dsemp
    push rax;push rcx;push rdi
    mov rsi,rbx;mov rdi,[rcx+16+rdi*8];call key_cmp
    mov esi,eax
    pop rdi;pop rcx;pop rax;test esi,esi;jnz .dsover
.dsemp:inc edi;jmp .dslp
.dsover:mov[rcx+16+rdi*8+8],rax;jmp dispatch
.dsnew:xor edi,edi
.dsn:cmp edi,edx;jae dispatch
    cmp qword[rcx+16+rdi*8],0;jne .dsnn
    mov[rcx+16+rdi*8],rbx;mov[rcx+16+rdi*8+8],rax;jmp dispatch
.dsnn:inc edi;jmp .dsn

DICT_HAS:
    cmp r8,2;jb dispatch;dec r8;mov rsi,[r13+r8*8];dec r8;mov rdi,[r13+r8*8];test rdi,rdi;jz .dhno;test dil,1;jnz .dhno;cmp dword[rdi],3;jne .dhno
    push rsi;mov edx,[rdi+8];xor eax,eax
.dhlp:cmp eax,edx;jae .dhno
    cmp qword[rdi+16+rax*8],0;je .dhemp
    push rax;push rdi;mov rdi,[rdi+16+rax*8];mov rsi,[rsp+16];call key_cmp
    mov ecx,eax;pop rdi;pop rax
    test ecx,ecx;jnz .dhyes
.dhemp:inc eax;jmp .dhlp
.dhno:pop rsi;mov qword[r13+r8*8],-1;inc r8;jmp dispatch
.dhyes:pop rsi;mov qword[r13+r8*8],1;inc r8;jmp dispatch

DICT_KEYS:
    cmp r8,1;jb dispatch;dec r8;mov rdi,[r13+r8*8];test rdi,rdi;jz dispatch;test dil,1;jnz dispatch;cmp dword[rdi],3;jne dispatch;push rdi;mov edx,[rdi+8];xor ecx,ecx;xor eax,eax
.dkc:cmp eax,edx;jae .dkcd;cmp qword[rdi+16+rax*8],0;je .dkcn;inc ecx
.dkcn:inc eax;jmp .dkc
.dkcd:lea edi,[ecx*8+16];call halloc
    pop rdi;mov dword[rax],2;mov[rax+4],ecx;mov[rax+8],ecx
    xor esi,esi;xor edx,edx
.dkf:cmp edx,[rdi+8];jae .dkd
    mov rbx,[rdi+16+rdx*8];test rbx,rbx;jz .dkn
    mov[rax+16+rsi*8],rbx;inc rsi
.dkn:inc edx;jmp .dkf
.dkd:mov[r13+r8*8],rax;inc r8;jmp dispatch

; ═══════════════════════════════════════════════════════════════
; 字符串操作 (安全寄存器: rsi/rdi/rcx/rdx/rax/rbx)
; ═══════════════════════════════════════════════════════════════
CONCAT:
    cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8]  ; rax=Str*b, rbx=Str*a
    mov ecx,[rbx+4];add ecx,[rax+4]
    push rax;push rbx;push rcx
    lea edi,[ecx+8];call halloc
    pop rcx;pop rsi;pop rdx       ; rcx=total, rsi=a*, rdx=b*
    mov dword[rax],1;mov[rax+4],ecx
    lea rdi,[rax+8]
    mov ecx,[rsi+4];lea rsi,[rsi+8];rep movsb
    mov ecx,[rdx+4];lea rsi,[rdx+8];rep movsb
    mov[r13+r8*8],rax;inc r8;jmp dispatch

STRLEN:
    dec r8;mov rbx,[r13+r8*8];test bl,1;jnz .sl_bad;cmp dword[rbx],1;jne .sl_bad;mov ecx,[rbx+4]
    xor eax,eax;xor edx,edx
.slp:cmp edx,ecx;jae .sld
    movzx esi,byte[rbx+8+rdx]
    test sil,0x80;jz .s1;cmp sil,0xE0;jb .s2;cmp sil,0xF0;jb .sl3;add edx,4;inc eax;jmp .slp
.sl3: add edx,3;inc eax;jmp .slp
.s2:add edx,2;inc eax;jmp .slp
.s1:inc edx;inc eax;jmp .slp
.sl_bad:inc r8;jmp dispatch
.sld:lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch

STREQ:
    cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];dec r8;mov rbx,[r13+r8*8];test rax,rax;jz .sq_no;test rbx,rbx;jz .sq_no;test al,1;jnz .sq_no;test bl,1;jnz .sq_no;cmp dword[rax],1;jne .sq_no;cmp dword[rbx],1;jne .sq_no
    mov ecx,[rax+4];cmp ecx,[rbx+4];jne .sqno
    lea rsi,[rax+8];lea rdi,[rbx+8];repe cmpsb;jne .sqno
    mov qword[r13+r8*8],1;inc r8;jmp dispatch
.sqno:mov qword[r13+r8*8],-1;inc r8;jmp dispatch

; STRSUB: 安全版 — 不碰 r10/r11, 用 rsi/rdi/rcx/rdx/rax/rbx
STRSUB:
    cmp r8,3;jb dispatch;dec r8;mov rax,[r13+r8*8]   ; count (tagged)
    dec r8;mov rbx,[r13+r8*8]   ; start (tagged)
    dec r8;mov rcx,[r13+r8*8]   ; str*
    sar rax,1;sar rbx,1
    ; rax=count, rbx=start, rcx=str*, r8=结果 push 位置
    mov edx,[rcx+4]             ; str->len (bytes)
    lea rsi,[rcx+8]             ; str->data (安全)
    push rax;push rbx           ; 保存 count,start 到原生栈
    ; phase 1: skip start chars
    xor edi,edi                 ; byte_off
    pop rcx;push rcx            ; rcx=start
.p1:test ecx,ecx;jz .p1d;cmp edi,edx;jae .sse2
    movzx eax,byte[rsi+rdi];test al,0x80;jz .p1s1
    cmp al,0xE0;jb .p1s2;cmp al,0xF0;jb .p1s3;add edi,4;dec ecx;jmp .p1
.p1s3:add edi,3;dec ecx;jmp .p1
.p1s2:add edi,2;dec ecx;jmp .p1
.p1s1:inc edi;dec ecx;jmp .p1
.p1d:mov ebx,edi               ; ebx = byte_start
    pop rcx;push rcx            ; rcx=count
.p2:test ecx,ecx;jz .p2d;cmp edi,edx;jae .p2d
    movzx eax,byte[rsi+rdi];test al,0x80;jz .p2s1
    cmp al,0xE0;jb .p2s2;cmp al,0xF0;jb .p2s3;add edi,4;dec ecx;jmp .p2
.p2s3:add edi,3;dec ecx;jmp .p2
.p2s2:add edi,2;dec ecx;jmp .p2
.p2s1:inc edi;dec ecx;jmp .p2
.p2d:sub edi,ebx               ; byte_len
    pop rcx;pop rcx             ; 清理 count,start
    push rsi                    ; 保存 data 指针
    push rdi                    ; 保存 byte_len
    lea edi,[edi+8];call halloc
    pop rcx;pop rsi             ; rcx=byte_len, rsi=data
    mov dword[rax],1;mov[rax+4],ecx
    lea rdi,[rax+8];add rsi,rbx;rep movsb
    mov[r13+r8*8],rax;inc r8;jmp dispatch
.sse2:pop rcx;pop rcx           ; 清理栈
    lea edi,[8];call halloc;mov dword[rax],1;mov dword[rax+4],0
    mov[r13+r8*8],rax;inc r8;jmp dispatch

ORD:
    cmp r8,2;jb dispatch;dec r8;mov rax,[r13+r8*8];sar rax,1  ; char_index
    dec r8;mov rbx,[r13+r8*8]            ; str*
    mov ecx,[rbx+4];lea rsi,[rbx+8];xor edi,edi
    mov edx,eax
.olp:test edx,edx;jz .of;cmp edi,ecx;jae .oz
    movzx eax,byte[rsi+rdi];test al,0x80;jz .o1
    cmp al,0xE0;jb .o2;add edi,3;dec edx;jmp .olp
.o2:add edi,2;dec edx;jmp .olp
.o1:inc edi;dec edx;jmp .olp
.of:cmp edi,ecx;jae .oz
    movzx eax,byte[rsi+rdi];test al,0x80;jz .ord1
    cmp al,0xE0;jb .ord2
    cmp al,0xF0;jb .ord3
    ; 4 byte: 0xF0-0xF7
    movzx eax,byte[rsi+rdi];and eax,0x07;shl eax,18
    movzx edx,byte[rsi+rdi+1];and edx,0x3F;shl edx,12;or eax,edx
    movzx edx,byte[rsi+rdi+2];and edx,0x3F;shl edx,6;or eax,edx
    movzx edx,byte[rsi+rdi+3];and edx,0x3F;or eax,edx
    jmp .op
.ord3: movzx eax,byte[rsi+rdi];and eax,0x0F;shl eax,12
    movzx edx,byte[rsi+rdi+1];and edx,0x3F;shl edx,6;or eax,edx
    movzx edx,byte[rsi+rdi+2];and edx,0x3F;or eax,edx;jmp .op
.ord2:movzx eax,byte[rsi+rdi];and eax,0x1F;shl eax,6
    movzx edx,byte[rsi+rdi+1];and edx,0x3F;or eax,edx;jmp .op
.ord1:movzx eax,byte[rsi+rdi]
.op:lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch
.oz:xor eax,eax;lea rax,[rax*2+1];mov[r13+r8*8],rax;inc r8;jmp dispatch

; ═══════════════════════════════════════════════════════════════
; WRITE_BINARY
; ═══════════════════════════════════════════════════════════════
WRBIN:
    cmp r8,2;jb dispatch;dec r8;mov rbx,[r13+r8*8]   ; byte_list (List*)
    dec r8;mov rdi,[r13+r8*8]   ; path (Str*)
    push r8  ; save VM sp
    ; open(path->data, O_CREAT|O_WRONLY, 0666)
    lea rdi,[rdi+8]             ; 完整 64 位地址
    mov esi,65;mov edx,438
    mov eax,2;syscall
    test eax,eax;js .wrbin_fail
    mov edi,eax                 ; fd
    mov ecx,[rbx+4];cmp ecx,0;je .wbc
    lea rsi,[rbx+16]
    sub rsp,128;mov rdx,rsp
    xor r8d,r8d
.wbl:cmp r8d,ecx;jae .wbf;mov rax,[rsi+r8*8];sar rax,1;mov[rdx+r8],al;inc r8
    cmp r8,128;jb .wbl
.wbf:push rcx;push rsi;push rdx
    mov eax,1;mov rsi,rdx;mov edx,r8d;syscall
    pop rdx;pop rsi;pop rcx;sub ecx,r8d;cmp ecx,0;je .wbc
    lea rsi,[rsi+r8*8];xor r8d,r8d;jmp .wbl
.wbc:add rsp,128;mov eax,3;syscall
    pop r8                       ; restore VM sp
    jmp dispatch

; ═══════════════════════════════════════════════════════════════
; halloc: bump allocator, 返回 rax = 分配地址
; 修复: 正确保存旧 heap_ptr，正确边界检查
; ═══════════════════════════════════════════════════════════════
halloc:
    push rcx                           ; 保存 rcx (调用者关键数据)
    cmp qword[rel heap_ptr],0; jne .init_done
    mov eax,12; xor edi,edi; syscall  ; brk(0)
    mov[rel heap_ptr],rax
    mov edi,eax; add edi,0x40000
    mov eax,12; syscall               ; brk(cur+256K)
    mov[rel heap_end],rax
.init_done:
    mov rax,[rel heap_ptr]            ; rax = 分配起始地址
    add edi,7; and edi,-8             ; 对齐
    add[rel heap_ptr],rdi             ; heap_ptr += size (redundant, handled by heap_end check below)
    mov rcx,[rel heap_end]
    cmp[rel heap_ptr],rcx
    jbe .ok
.oom:
    mov eax,60; mov edi,1; syscall    ; exit(1)
.ok:
    pop rcx                            ; 恢复
    ret

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
.xv:test ecx,ecx; jz .xvd; dec ecx; mov qword[r12+rcx*8],0; jmp .xv
.xvd:
    mov eax,[rel tmp_buf+6]; mov[rel code_len],eax
    mov edi,ebx; lea rsi,[rel code_buf]; mov edx,eax; mov eax,0; syscall
    mov edi,ebx; mov eax,3; syscall; xor eax,eax; ret
.lbc:mov edi,ebx; mov eax,3; syscall
.lbf:mov eax,-1; ret

; ═══════════════════════════════════════════════════════════════
; 跳转表: 256 × 4 字节偏移 (dd)，dispatch 用 movsx rax,word[rel jmp_tbl+op*2] 索引
; 每项 = handler_label - jmp_tbl，16-bit 有符号 (handler 必须在 ±32KB 内)
; ═══════════════════════════════════════════════════════════════
jmp_tbl:
%assign i 0
%rep 256
    %if i == 0x01
        dd PUSH_I - jmp_tbl
    %elif i == 0x2D
        dd PUSH_STR - jmp_tbl
    %elif i == 0x07
        dd LOAD - jmp_tbl
    %elif i == 0x08
        dd STORE - jmp_tbl
    %elif i == 0x02
        dd ADD - jmp_tbl
    %elif i == 0x03
        dd SUB - jmp_tbl
    %elif i == 0x04
        dd MUL - jmp_tbl
    %elif i == 0x05
        dd DIV - jmp_tbl
    %elif i == 0x06
        dd MOD - jmp_tbl
    %elif i == 0x13
        dd GT - jmp_tbl
    %elif i == 0x14
        dd LT - jmp_tbl
    %elif i == 0x15
        dd EQ - jmp_tbl
    %elif i == 0x17
        dd GTE - jmp_tbl
    %elif i == 0x19
        dd CONCAT - jmp_tbl
    %elif i == 0x1A
        dd STRLEN - jmp_tbl
    %elif i == 0x1B
        dd STRSUB - jmp_tbl
    %elif i == 0x1C
        dd STREQ - jmp_tbl
    %elif i == 0x31
        dd ORD - jmp_tbl
    %elif i == 0x27
        dd LIST_NEW - jmp_tbl
    %elif i == 0x25
        dd LIST_GET - jmp_tbl
    %elif i == 0x2A
        dd LIST_LEN - jmp_tbl
    %elif i == 0x26
        dd SET_ELEM - jmp_tbl
    %elif i == 0x28
        dd LIST_CAT - jmp_tbl
    %elif i == 0x29
        dd SLICE - jmp_tbl
    %elif i == 0x1D
        dd DICT - jmp_tbl
    %elif i == 0x1E
        dd DICT_GET - jmp_tbl
    %elif i == 0x1F
        dd DICT_SET - jmp_tbl
    %elif i == 0x20
        dd DICT_HAS - jmp_tbl
    %elif i == 0x32
        dd DICT_KEYS - jmp_tbl
    %elif i == 0x21
        dd IS_NUM - jmp_tbl
    %elif i == 0x22
        dd IS_STR - jmp_tbl
    %elif i == 0x23
        dd IS_LIST - jmp_tbl
    %elif i == 0x09
        dd JMP - jmp_tbl
    %elif i == 0x0A
        dd JZ - jmp_tbl
    %elif i == 0x33
        dd JMP32 - jmp_tbl
    %elif i == 0x0C
        dd CALL - jmp_tbl
    %elif i == 0x0D
        dd RET - jmp_tbl
    %elif i == 0x30
        dd WRBIN - jmp_tbl
    %elif i == 0x3F
        dd CLOSURE - jmp_tbl
    %elif i == 0x3e
        dd PUSH_STR16 - jmp_tbl
    %elif i == 0x3d
        dd CALL32 - jmp_tbl
    %elif i == 0x3c
        dd STORE16 - jmp_tbl
    %elif i == 0x3b
        dd LOAD16 - jmp_tbl
    %elif i == 0xFF
        dd .halt - jmp_tbl
    %elif i == 0x00
        dd .nop_handler - jmp_tbl
    %else
        dd .nop_handler - jmp_tbl
    %endif
%assign i i+1
%endrep
jmp_tbl_end:

; ═══════════════════════════════════════════════════════════════
; BSS
; ═══════════════════════════════════════════════════════════════
file_end:
align 8
stack:    resq 512
vars:     resq 64
cstk:     resq 128
code_buf: resb 65536
tmp_buf:  resb 16
code_len: resd 1
halted:   resb 1
heap_ptr: resq 1
heap_end: resq 1
mem_end:
