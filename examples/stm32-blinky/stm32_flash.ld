/* STM32F103C8T6 链接脚本 (64KB Flash, 20KB SRAM) */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 64K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 20K
}

SECTIONS
{
    .text :
    {
        KEEP(*(.isr_vector))
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    .data : AT(_etext)
    {
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM

    .bss :
    {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /* 强制导出 BSS 段符号，避免 arm-none-eabi-gcc 优化掉 */
    PROVIDE(_sbss = _sbss);
    PROVIDE(_ebss = _ebss);

    _estack = ORIGIN(RAM) + LENGTH(RAM);
}

/* 导出调试/监控用符号 */
PROVIDE(_firmware_start = 0x08000000);
PROVIDE(_flash_size = 64K);
PROVIDE(_ram_size = 20K);
