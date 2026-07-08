/* FFI M3 夹具：覆盖类型映射/typedef/struct/enum/变参拒/函数指针拒（无 include，可 --no-preprocess） */

typedef int myint;

struct Point {
    int x;
    int y;
};

enum Status { OK = 0, FAIL = 1, RETRY };

int add(int a, int b);
myint twice(myint v);
const char *echo(const char *s);
void *openf(const char *path);
double scale(double v, float k);
unsigned long long big(unsigned long long n);
void ping(void);

/* 阶段 1 拒绝面 */
int logf_style(const char *fmt, ...);
int apply(int (*f)(int), int v);
