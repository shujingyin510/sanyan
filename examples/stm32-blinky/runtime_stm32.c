#include <stdint.h>

#include "firmware_data.h"

#define PERIPH_BASE      0x40000000UL
#define APB2PERIPH_BASE  (PERIPH_BASE + 0x10000UL)
#define AHBPERIPH_BASE   (PERIPH_BASE + 0x20000UL)
#define RCC_BASE         (AHBPERIPH_BASE + 0x1000UL)
#define RCC_APB2ENR      (*(volatile uint32_t *)(RCC_BASE + 0x18))
#define GPIOC_BASE       (APB2PERIPH_BASE + 0x1000UL)
#define GPIOA_BASE       (APB2PERIPH_BASE + 0x0800UL)
#define GPIO_CRH(p)      (*(volatile uint32_t *)((p) + 0x04))
#define GPIO_BSRR(p)     (*(volatile uint32_t *)((p) + 0x10))
#define GPIO_BRR(p)      (*(volatile uint32_t *)((p) + 0x14))

/* USART1 @ 0x40013800 */
#define USART1_BASE      (APB2PERIPH_BASE + 0x3800UL)
#define USART_SR(p)      (*(volatile uint32_t *)((p) + 0x00))
#define USART_DR(p)      (*(volatile uint32_t *)((p) + 0x04))
#define USART_CR1(p)     (*(volatile uint32_t *)((p) + 0x0C))
#define USART_SR_TXE     (1 << 7)

/* SysTick */
#define STK_CSR          (*(volatile uint32_t *)(0xE000E010))
#define STK_RVR          (*(volatile uint32_t *)(0xE000E014))
#define STK_CVR          (*(volatile uint32_t *)(0xE000E018))

#define STACK_MAX 64
static int32_t _stack[STACK_MAX];
static int16_t _sp;

#define FIRMWARE_VARS 2
static int32_t _vars[FIRMWARE_VARS];

typedef int32_t (*native_read_fn)(uint8_t id);
typedef void    (*native_write_fn)(uint8_t id, int32_t val);
static native_read_fn  _read_devs[16];
static native_write_fn _write_devs[16];

static volatile uint32_t _ticks;
static int _uart_ready;

void vm_register_device(uint8_t id, native_read_fn r, native_write_fn w) {
    if (id < 16) { _read_devs[id] = r; _write_devs[id] = w; }
}

static inline void push(int32_t v) {
    if (_sp >= STACK_MAX) return;
    _stack[_sp++] = v;
}

static inline int32_t pop(void) {
    if (_sp <= 0) return 0;
    return _stack[--_sp];
}

static int32_t led_read(uint8_t id) { (void)id; return 0; }
static void led_write(uint8_t id, int32_t val) {
    (void)id;
    if (val) GPIO_BRR(GPIOC_BASE) = (1 << 13);
    else     GPIO_BSRR(GPIOC_BASE) = (1 << 13);
}

void SysTick_Handler(void) { _ticks++; }

static void delay_ms(uint32_t ms) {
    uint32_t start = _ticks;
    while (_ticks - start < ms);
}

/* ── UART ──────────────────────────────────────── */
static void uart_init(void) {
    RCC_APB2ENR |= (1 << 2) | (1 << 14);
    RCC_APB2ENR; RCC_APB2ENR;

    uint32_t crh = *(volatile uint32_t *)(GPIOA_BASE + 0x04);
    crh = (crh & ~0xFFFFFF0F) | 0x000004B0;
    *(volatile uint32_t *)(GPIOA_BASE + 0x04) = crh;

    *(volatile uint32_t *)(USART1_BASE + 0x08) = 4; /* BRR first */
    USART_CR1(USART1_BASE) = 0;
    USART_CR1(USART1_BASE) = (1 << 13) | (1 << 3) | (1 << 2);
}
static void uart_putchar(char c) {
    while (!(USART_SR(USART1_BASE) & USART_SR_TXE));
    USART_DR(USART1_BASE) = c;
}
static void uart_puts(const char *s) { while (*s) uart_putchar(*s++); }
static void uart_print_int(int32_t n) {
    char buf[12]; int i = 11; buf[11] = '\0';
    if (n < 0) { uart_putchar('-'); n = -n; }
    do { buf[--i] = '0' + (n % 10); n /= 10; } while (n);
    uart_puts(buf + i);
}

void vm_run(void) {
    const uint8_t *code = firmware_code;
    uint32_t pc = 0;
    while (1) {
        uint8_t op = code[pc++];
        int32_t a, b;
        switch (op) {
        case 0x01: /* PUSH_I */
            a = (int32_t)(code[pc] | (code[pc+1]<<8) | (code[pc+2]<<16) | (code[pc+3]<<24));
            pc += 4; push(a); break;
        case 0x02: b = pop(); a = pop(); push(a + b); break;
        case 0x03: b = pop(); a = pop(); push(a - b); break;
        case 0x04: b = pop(); a = pop(); push(a * b); break;
        case 0x05: b = pop(); a = pop(); if (b) push(a / b); else push(0); break;
        case 0x06: b = pop(); a = pop(); if (b) push(a % b); else push(0); break;
        case 0x07: /* LOAD */
            a = code[pc++];
            if (a < FIRMWARE_VARS) push(_vars[a]);
            break;
        case 0x08: /* STORE */
            a = code[pc++];
            if (a < FIRMWARE_VARS) _vars[a] = pop();
            break;
        case 0x09: /* JMP */
            a = (int16_t)(code[pc] | (code[pc+1] << 8));
            pc += 2 + a;
            break;
        case 0x0A: /* JZ */
            a = (int16_t)(code[pc] | (code[pc+1] << 8));
            pc += 2;
            if (pop() == 0) pc += a;
            break;
        case 0x0B: /* JNZ */
            a = (int16_t)(code[pc] | (code[pc+1] << 8));
            pc += 2;
            if (pop() != 0) pc += a;
            break;
        case 0x0E: /* PRINT */
            if (!_uart_ready) { uart_init(); _uart_ready = 1; }
            a = pop(); uart_print_int(a); uart_puts("\r\n"); break;
        case 0x0F: /* IO_READ */
            a = (uint8_t)pop();
            if (a < 16 && _read_devs[a]) push(_read_devs[a](a));
            else push(0);
            break;
        case 0x10: /* IO_WRITE */
            a = pop(); b = (uint8_t)pop();
            if (b < 16 && _write_devs[b]) _write_devs[b](b, a);
            break;
        case 0x18: /* WAIT */
            a = pop();
            if (a > 0) delay_ms((uint32_t)a);
            break;
        case 0xFF: /* HALT */
            return;
        default: break;
        }
    }
}

void init(void) {
    RCC_APB2ENR |= (1 << 4);
    uint32_t crh = GPIO_CRH(GPIOC_BASE);
    crh = (crh & ~(0xF << 20)) | (0x2 << 20);
    GPIO_CRH(GPIOC_BASE) = crh;
    GPIO_BSRR(GPIOC_BASE) = (1 << 13);

    /* SysTick 1ms @ 8MHz HSI */
    STK_RVR = 8000 - 1;
    STK_CVR = 0;
    STK_CSR = (1 << 0) | (1 << 2) | (1 << 1);

    vm_register_device(13, led_read, led_write);
}

void _start(void);
void Default_Handler(void) { while (1); }
void SysTick_Handler(void);

extern uint32_t _estack;

__attribute__((section(".isr_vector")))
void (*const g_pfnVectors[48])(void) = {
    (void(*)(void))&_estack,
    _start,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, SysTick_Handler,
    [16 ... 47] = Default_Handler,
};

/* 清零宏：确保所有 BSS 变量初始化，不依赖链接脚本符号 */
#define ZERO_VAR(var) __builtin_memset(&(var), 0, sizeof(var))

void _start(void) {
    extern uint32_t _sbss[], _ebss[];
    /* 标准 BSS 清零循环（若 _sbss/_ebss 链接正确） */
    for (uint32_t *p = _sbss; p < _ebss; p++) *p = 0;
    /* 防御性显式清零：防止链接脚本符号缺失 */
    ZERO_VAR(_sp);
    ZERO_VAR(_ticks);
    ZERO_VAR(_uart_ready);
    ZERO_VAR(_read_devs);
    ZERO_VAR(_write_devs);
    ZERO_VAR(_vars);
    init();
    vm_run();
    while (1);
}
