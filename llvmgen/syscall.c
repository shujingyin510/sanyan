/* syscall.c — Windows 原生层：I/O + 内存分配 + 运行时桩 */
#include <windows.h>

/* 全局寄存器计数器 */
static long long _reg_id = 0;
long long _next_reg_id(void) { return ++_reg_id; }

void san_sys_write(int fd, const char *buf, int len) {
    HANDLE h;
    if (fd == 1) h = GetStdHandle(STD_OUTPUT_HANDLE);
    else if (fd == 2) h = GetStdHandle(STD_ERROR_HANDLE);
    else return;
    DWORD written;
    WriteFile(h, buf, (DWORD)len, &written, NULL);
}

void *_rt_malloc(int size) {
    return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size);
}

void _rt_free(void *ptr) {
    HeapFree(GetProcessHeap(), 0, ptr);
}

/* ── 运行时桩函数 ── */
/* 浮点打印: 暂用整数近似 */
void rt_print_float(void *f) {
    (void)f;
}

/* ── 文件 I/O ── */
char *san_read_file(const char *path, int *out_len) {
    // 支持字符串对象: 检查type=1
    if (path && *(int *)path == 1) path += 8;
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ,
                           NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return NULL;
    DWORD size = GetFileSize(h, NULL);
    char *buf = (char *)_rt_malloc((int)size + 1);
    if (!buf) { CloseHandle(h); return NULL; }
    DWORD rd;
    ReadFile(h, buf, size, &rd, NULL);
    buf[rd] = 0;
    CloseHandle(h);
    if (out_len) *out_len = (int)rd;
    return buf;
}

void san_write_file(const char *path, const char *buf, int len) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD wr;
    WriteFile(h, buf, (DWORD)len, &wr, NULL);
    CloseHandle(h);
}

void __chkstk(void) {}
