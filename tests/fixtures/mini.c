/* M4 运行时测试用实现（gcc 缺席时相关测试整体 skip） */
#include "mini.h"
#include <stddef.h>

int add(int a, int b) { return a + b; }
myint twice(myint v) { return v * 2; }
const char *echo(const char *s) { return s; }
void *openf(const char *path) { return (void *)0; } /* 恒 NULL：err=null_ret 惯例夹具 */
double scale(double v, float k) { return v * k; }
unsigned long long big(unsigned long long n) { return n + 1; }
void ping(void) {}
int logf_style(const char *fmt, ...) { return 0; }
int apply(int (*f)(int), int v) { return f(v); }
