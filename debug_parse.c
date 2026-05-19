#include <stdint.h>
#include <stdio.h>
extern void *parse_sanyan(const char *source);
int main() {
    void *ast = parse_sanyan("hello");
    printf("%s\n", ast ? "OK" : "NULL");
    return 0;
}
