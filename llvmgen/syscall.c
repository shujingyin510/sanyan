/* syscall.c — Windows 原生 syscall，零 stdio 依赖 */
#include <windows.h>

void san_sys_write(int fd, const char *buf, int len) {
    HANDLE h;
    if (fd == 1) {
        h = GetStdHandle(STD_OUTPUT_HANDLE);
    } else if (fd == 2) {
        h = GetStdHandle(STD_ERROR_HANDLE);
    } else {
        return;
    }
    DWORD written;
    WriteFile(h, buf, (DWORD)len, &written, NULL);
}
