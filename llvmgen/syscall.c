/* syscall.c — Windows 原生层：I/O + 内存分配，零 stdio/libc 依赖 */
#include <windows.h>

void san_sys_write(int fd, const char *buf, int len) {
    HANDLE h;
    if (fd == 1) h = GetStdHandle(STD_OUTPUT_HANDLE);
    else if (fd == 2) h = GetStdHandle(STD_ERROR_HANDLE);
    else return;
    DWORD written;
    WriteFile(h, buf, (DWORD)len, &written, NULL);
}

void *_rt_malloc(int size) {
    return HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size);
}

void _rt_free(void *ptr) {
    HeapFree(GetProcessHeap(), 0, ptr);
}

/* __chkstk: Windows x64 栈探测，alloca 需要 */
void __chkstk(void) {}
