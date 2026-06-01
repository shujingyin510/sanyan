# 三言形式化验证 Makefile
# 需要: coqc (Coq ≥ 8.16)

COQFLAGS = -R . SanyanFormal

TARGETS = Trit.vo AgentMap.vo TaggedPtr.vo

.PHONY: all clean check

all: $(TARGETS)

%.vo: %.v
	coqc $(COQFLAGS) $<

check: all
	@echo "=== 所有 Coq 模块编译通过，定理证明完成 ==="

clean:
	rm -f *.vo *.vos *.vok *.glob .*.aux
