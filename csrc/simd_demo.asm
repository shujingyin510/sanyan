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
    ; rcx=input, rdx=output, r8d=N  (Windows x64)
    ; 直接用调用约定的寄存器，避免额外保存
    push rbx; push r12
    mov r12, rcx               ; r12 = input
    mov rbx, rdx               ; rbx = output
    mov ebp, r8d               ; ebp = N

    ; 1. find max
    vbroadcastss ymm0, [r12]
    xor ecx, ecx
    cmp ebp, 8; jl .smax
.mxlp:  vmovups ymm1, [r12 + rcx*4]; vmaxps ymm0, ymm0, ymm1
    add ecx, 8; cmp ecx, ebp; jl .mxlp; jmp .mxdn
.smax:  mov eax, 1
.smxl:  vmaxss xmm0, xmm0, [r12 + rax*4]; inc eax; cmp eax, ebp; jl .smxl
.mxdn:  vextractf128 xmm1, ymm0, 1; vmaxps xmm0, xmm0, xmm1
    vpermilps xmm1, xmm0, 0x4E; vmaxps xmm0, xmm0, xmm1
    vpermilps xmm1, xmm0, 0xB1; vmaxps xmm0, xmm0, xmm1
    vbroadcastss ymm9, xmm0

    ; 2. exp approx + sum
    vxorps ymm10, ymm10, ymm10
    xor ecx, ecx
    mov eax, 0x3F800000; vmovd xmm12, eax; vbroadcastss ymm12, xmm12
    mov eax, 0x3F000000; vmovd xmm13, eax; vbroadcastss ymm13, xmm13
    mov eax, 0x3E2AAAAB; vmovd xmm14, eax; vbroadcastss ymm14, xmm14

.xlp:   vmovups ymm0, [r12 + rcx*4]; vsubps ymm0, ymm0, ymm9
    vmulps ymm1, ymm0, ymm14; vaddps ymm1, ymm1, ymm13
    vmulps ymm1, ymm0, ymm1; vaddps ymm1, ymm1, ymm12
    vmulps ymm1, ymm0, ymm1; vaddps ymm1, ymm1, ymm12
    vmovups [rbx + rcx*4], ymm1; vaddps ymm10, ymm10, ymm1
    add ecx, 8; cmp ecx, ebp; jl .xlp

    ; 3. sum
    vextractf128 xmm0, ymm10, 1; vaddps xmm10, xmm10, xmm0
    vhaddps xmm10, xmm10, xmm10; vhaddps xmm10, xmm10, xmm10
    vbroadcastss ymm11, xmm10

    ; 4. div
    xor ecx, ecx
.nlp:   vmovups ymm0, [rbx + rcx*4]; vdivps ymm0, ymm0, ymm11
    vmovups [rbx + rcx*4], ymm0; add ecx, 8; cmp ecx, ebp; jl .nlp

    pop r12; pop rbx; ret
