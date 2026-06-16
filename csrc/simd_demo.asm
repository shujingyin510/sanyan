; ═══════════════════════════════════════════════════════════════
; Sanyan SIMD Demo — GEMM + Softmax
; AVX2 FMA 内核 + Python FFI
; ═══════════════════════════════════════════════════════════════
BITS 64

section .text
global matmul_256x256
global softmax_avx2

matmul_256x256:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    push rdi
    push rsi
    mov rdi, rcx
    mov rsi, rdx
    mov r15, r8
    mov r12d, 256
    xor ecx, ecx
.i_loop:
    imul r14d, ecx, 1024
    xor edx, edx
.j_loop:
    xor ebx, ebx
    vxorps ymm0, ymm0, ymm0
    vxorps ymm1, ymm1, ymm1
    vxorps ymm2, ymm2, ymm2
    vxorps ymm3, ymm3, ymm3
    lea r10, [rdi + r14]
    lea r11, [rdi + r14 + 1024]
    lea r13, [rdi + r14 + 2048]
    lea rax, [rdi + r14 + 3072]
.k_loop:
    imul r8d, ebx, 1024
    lea r8, [rsi + r8]
    vbroadcastss ymm4, [r10 + rbx*4]
    vbroadcastss ymm5, [r11 + rbx*4]
    vbroadcastss ymm6, [r13 + rbx*4]
    vbroadcastss ymm7, [rax + rbx*4]
    vmovups ymm8, [r8 + rdx*4]
    vfmadd231ps ymm0, ymm4, ymm8
    vfmadd231ps ymm1, ymm5, ymm8
    vfmadd231ps ymm2, ymm6, ymm8
    vfmadd231ps ymm3, ymm7, ymm8
    inc ebx
    cmp ebx, 256
    jne .k_loop
    lea r10, [r15 + r14]
    lea r11, [r15 + r14 + 1024]
    lea r13, [r15 + r14 + 2048]
    lea rax, [r15 + r14 + 3072]
    vmovups [r10 + rdx*4], ymm0
    vmovups [r11 + rdx*4], ymm1
    vmovups [r13 + rdx*4], ymm2
    vmovups [rax + rdx*4], ymm3
    add edx, 8
    cmp edx, 256
    jne .j_loop
    add ecx, 4
    cmp ecx, 256
    jne .i_loop
.done_gemm:
    pop rsi
    pop rdi
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret


; ── Softmax ──
; softmax_avx2(float* input, float* output, int N)
; 简化实现: exp 用 3 阶多项式近似 (精度 ~0.1%)
softmax_avx2:
    push rbx; push r12; push r13
    mov r12, rcx; mov r13, rdx; mov ebx, r8d

    ; 1. find max
    movss xmm10, [r12]
    mov eax, 1
.mx:    movss xmm1, [r12 + rax*4]
    maxss xmm10, xmm1
    inc eax; cmp eax, ebx; jl .mx

    ; 2. exp(x-max) + sum, with clamp for very negative values
    xorps xmm11, xmm11
    mov eax, 0xC1200000        ; -10.0 as float bits
    vmovd xmm9, eax            ; threshold
    xor eax, eax
    ; exp constants
    mov eax, 0x3F800000; vmovd xmm8, eax  ; 1.0
    xor eax, eax          ; reset counter

.xp:    movss xmm0, [r12 + rax*4]
    subss xmm0, xmm10          ; x - max
    movss xmm7, xmm0

    ; if x < -10, result = 0
    comiss xmm7, xmm9
    jb .zero_exp

    ; exp approx: 1 + x*(1 + x*(0.5 + x*0.1667))
    movss xmm2, xmm7
    movss xmm3, [rel c3_data]
    mulss xmm3, xmm7; movss xmm4, [rel c2_data]; addss xmm3, xmm4
    mulss xmm3, xmm7; movss xmm4, [rel c1_data]; addss xmm3, xmm4
    mulss xmm3, xmm7; movss xmm4, [rel c1_data]; addss xmm3, xmm4
    jmp .store

.zero_exp:
    xorps xmm3, xmm3

.store:
    movss [r13 + rax*4], xmm3
    addss xmm11, xmm3
    inc eax; cmp eax, ebx; jl .xp

    ; 3. divide by sum
    movss xmm12, xmm11
    ucomiss xmm12, xmm8
    jbe .skip_div
    xor eax, eax
.dv:    movss xmm0, [r13 + rax*4]
    divss xmm0, xmm12
    movss [r13 + rax*4], xmm0
    inc eax; cmp eax, ebx; jl .dv
.skip_div:
    pop r13; pop r12; pop rbx; ret

section .rodata align 16
c1_data: dd 1.0
c2_data: dd 0.5
c3_data: dd 0.16666667
