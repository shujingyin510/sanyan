/* dp.c — LLVM-compiled parse_sanyan 测试 */
#include <stdint.h>
#include <stdio.h>

extern void *parse_sanyan(const char *s);

static void test(const char *code) {
    void *ast = parse_sanyan(code);
    printf("%-30s -> %s\n", code, ast ? "OK" : "NULL");
}

int main() {
    test("42");
    test("\"hello\"");
    test("x");
    test("(add 1 2)");
    test("(if 1 2 3)");
    test("(set x 42)");
    test("(fn (f x) (return x))");
    return 0;
}
