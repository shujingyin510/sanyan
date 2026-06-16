# csrc/ — C 源码 & 推理引擎 & 基准测试

```
csrc/
├── README.md                    ← 本文件

├── ═══ C 算子库 ═══
├── transformer_c.c              C 源码: LayerNorm + GELU + Residual (45行)
├── transformer_c.dll            编译产物: Transformer 激活函数库
├── softmax_c.c                  C 源码: expf Softmax (19行)
├── softmax_c.dll                编译产物: Softmax 库
├── simd_demo.asm                AVX2 FMA GEMM 256×256 汇编内核
├── simd_demo.dll                编译产物: SIMD 矩阵乘法库

├── ═══ GPT-2 124M 推理 ═══
├── gpt2_engine.py              推理引擎 (GPT-2 架构, C LN + KV Cache)
├── gpt2_kv.py                  KV Cache 快速推理 (已验证 logit_diff=0.000046)
├── gpt2_bench.py               20 prompt 质量对比 (EOS vs 三元门控)
├── gpt2_scale.py               ★ 1000 prompt 全量基准 (三元=100% 停止率)
├── gpt2_blind.py               ★ 100 prompt 盲评材料生成
├── gpt2_blind_judge.py         盲评自动评判引擎
├── gpt_neo_engine.py           GPT-Neo 125M 推理 (已弃用, 模型质量差)

├── ═══ 三言语言验证 ═══
├── infer_demo.san              ★ .san 源码 — 三态推理演示 (S-表达式语法)
├── infer_demo.bin              编译产物: .san → .bin 字节码 (521字节)
├── sanyan_ops.py               ★ 算子注册模块 (reg_op: 初始化/推理循环/输出全部)
├── sanyan_run.py               ★ .san 运行器 (导入算子 + 解析 + 执行)
├── sanyan_infer_demo.py        旧版 Demo (内嵌 .san, 已被 sanyan_run.py 取代)
├── sanyan_gemm_demo.py         reg_op 示例: 注册 C GEMM 为三言原生函数
├── sanyan_parse.c              C 解析器源码
├── sanyan_parse.dll            C 解析器编译产物

├── ═══ Qwen2.5-0.5B 验证 ═══
├── qwen25_bench.py             ★ 1000 prompt UR 零误报验证 (假阳性 0.4%)
├── qwen_degen.py               ★ 诱导退化实验 (9 类坏 prompt)

├── ═══ 三态门控基准 (TinyStories) ═══
├── ternary_infer.py            三态门控推理引擎 v4 (轨迹检测)
├── ternary_bench.py            100 prompt 对比基准
├── ternary_scale.py            1000 prompt 大基准 (3.6M)
├── ternary_scale_28m.py        1000 prompt 大基准 (28M, 修正 UR=0.30)
├── quality_test.py             3.6M 模型质量测试
├── quality_28m.py              28M 模型质量测试

├── ═══ C VM / 编译器 ═══
├── runtime.c                   C VM 核心 (ISA v2 解释器, 61KB)
├── runtime_common.h            C VM 公共头文件
├── compile.c                   C 编译器前端
├── test_runtime.c              C VM 单元测试
├── harness.c                   C 测试框架
├── parse_harness.c             解析器测试
├── debug_parse.c               解析器调试
├── dp.c                        动态规划算法
├── sanyan_vm_seed.c            Level 3: C 种子 VM (318行, TCC 可编译)
├── sanyan_vm_l4.asm            Level 4: x86_64 NASM 汇编 VM (617行)

├── ═══ 模型文件 ═══
├── tinystories_1m.bin          TinyStories 3.6M 权重 (47MB)
├── tinystories_28m.bin         TinyStories 28M 权重 (230MB)
└── gpt2/                        GPT-2 124M 权重目录 (548MB, 镜像下载)
```

## 关键文件说明

### 推理引擎链路

```
.san 源码                  三言逻辑层
  ↓ sanyan_run.py
Python evaluator          调度层
  ↓ reg_op (sanyan_ops.py)
Python wrapper            算子封装层
  ↓ ctypes
C DLL (transformer_c.dll) C 算子层 (LayerNorm/GELU)
  ↓ numpy @
GPT-2 124M 推理          矩阵运算层
```

### 已验证的结论

| 结论 | 证据文件 |
|------|----------|
| UR=0.30 跨 4 模型 3 架构有效 | ternary_scale.py, gpt2_scale.py, qwen25_bench.py |
| KV Cache 正确性 (logit_diff=0.000046) | gpt2_kv.py |
| C LayerNorm 精度 (vs PyTorch diff=1e-7) | gpt2_engine.py |
| .san 能调度推理引擎 | infer_demo.san + sanyan_run.py |
| 消融: UR-only = 完整轨迹检测 | 全基准数据分析 |

### 运行方式

```bash
# GPT-2 推理
python -X utf8 csrc/gpt2_scale.py          # 1000 prompt 基准

# 三言语言验证
python -X utf8 csrc/sanyan_run.py csrc/infer_demo.san

# Qwen2.5 验证
python -X utf8 csrc/qwen25_bench.py        # 1000 prompt UR 检查
python -X utf8 csrc/qwen_degen.py          # 诱导退化实验

# C 算子编译
gcc -shared -O2 -o csrc/transformer_c.dll csrc/transformer_c.c -lm
nasm -f bin -o csrc/simd_demo.dll csrc/simd_demo.asm
```

## 文件大小

| 分类 | 文件数 | 总大小 |
|------|--------|--------|
| Python 脚本 | 21 | ~130 KB |
| C 源码 | 11 | ~190 KB |
| 汇编源码 | 2 | ~30 KB |
| 编译产物 (DLL/O) | 5 | ~390 KB |
| 模型文件 | 2 | ~280 MB |
| 其他 (.bin) | 2 | ~1 KB |
