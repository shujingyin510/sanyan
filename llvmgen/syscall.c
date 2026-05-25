/* syscall.c — 最小的 syscall 桩，替代 runtime.c 的 libc printf 依赖 */
#include <unistd.h>

void san_sys_write(int fd, const char *buf, int len) {
    write(fd, buf, len);
}

void _start_rt(void) {}  /* 占位，避免链接器报错 */
