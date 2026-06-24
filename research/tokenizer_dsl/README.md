# Tokenizer-语言对齐实验

> Tokenizer 词表设计是否决定了中文 DSL 在 LLM 代码生成中的可行性？

## 方法

11 组等价代码片段，两种语法：
- **中文 DSL**：`循环 10 次：\n    打印 i`（中文关键词、全角标点）
- **Python**：`for i in range(10):\n    print(i)`

4 个 tokenizer（均 ≤0.5B、可本地运行）：

| Tokenizer | 词表 | 训练语料 | 中文支持 |
|-----------|------|---------|---------|
| GPT-2 124M | 50,257 | 英语网页 | ❌ 无 |
| OPT-125M | 50,265 | 英语学术+书籍 | ❌ 无 |
| Pythia-160M | 50,254 | The Pile（多语） | △ 弱 |
| Qwen2.5-0.5B | 151,643 | 中英双语 | ✅ 强 |

## 结果

### 总览

| Tokenizer | 词表 | 中文 avg | Python avg | 差距 |
|-----------|------|---------|-----------|------|
| GPT-2 (OpenAI) | 50k | 30.5 tk | 16.3 tk | **-88%** |
| OPT-125M (Meta) | 50k | 31.5 tk | 17.3 tk | **-83%** |
| Pythia-160M (Eleuther) | 50k | 21.2 tk | 14.0 tk | **-51%** |
| Qwen2.5-0.5B (阿里) | 151k | 16.6 tk | 13.3 tk | **-25%** |

> 负值 = 中文比 Python 多消耗 token（不利中文）。0% = 持平，正值 = 中文更少。

### 逐模式对比（11 组 × 4 tokenizer）

| 模式 | GPT2 Δ | Qwen Δ | OPT Δ | Pythia Δ |
|------|--------|--------|-------|----------|
| For 循环 | -47% | -8% | -44% | -15% |
| While 循环 | -21% | **+0%** | -20% | **+0%** |
| Return | -50% | **+0%** | -43% | -17% |
| 变量赋值 | -78% | -10% | -70% | -56% |
| If/else | -96% | -33% | -92% | -50% |
| 函数定义 | -80% | -9% | -75% | -38% |
| 文件读取 | -80% | -13% | -76% | -28% |
| 列表推导 | -86% | -27% | -80% | -69% |
| 类定义 | -85% | -44% | -82% | -63% |
| Try/catch | -136% | -47% | -130% | -94% |
| Dict 推导 | -162% | -62% | -150% | -100% |
| **TOTAL** | **-88%** | **-25%** | **-83%** | **-51%** |

### 逐词 token 切分

每个中文关键词在 GPT-2 vs Qwen 下切分对比：

| 中文词 | GPT2 tk | GPT2 切分 | Qwen tk | Qwen 切分 |
|--------|---------|----------|---------|----------|
| 循环 | 5 | 字节碎片 ×5 | 1 | `循环` |
| 如果 | 5 | 字节碎片 ×5 | 1 | `如果` |
| 否则 | 4 | 字节碎片 ×4 | 1 | `否则` |
| 打印 | 4 | 字节碎片 ×4 | 1 | `打印` |
| 函数 | 4 | 字节碎片 ×4 | 1 | `函数` |
| 返回 | 4 | 字节碎片 ×4 | 1 | `返回` |
| 类 | 3 | 字节碎片 ×3 | 1 | `类` |
| 导入 | 4 | 字节碎片 ×4 | 1 | `导入` |
| 捕获 | 6 | 字节碎片 ×6 | 2 | `捕`+`获` |

根因：GPT-2 tokenizer 不认识中文，每个汉字（UTF-8 3 字节）被切成 2-3 个无意义字节 token。例如 `循`（e5beaa）→ 2 token，`环`（e78eaf）→ 3 token，`循环` = 5 token。Qwen 直接 1 token。

## 核心发现

1. **英语优化 tokenizer 是中文 DSL 的硬瓶颈**。GPT-2/OPT（50k 纯英语词表）让中文 DSL 比 Python 多 83-88% token。不是语法差，是 tokenizer 不认识中文。

2. **词表规模其次，中文覆盖率第一**。GPT-2/OPT/Pythia 词表大小相近（~50k），但 Pythia 差距（-51%）明显小于前两者（-88%/-83%）。Pythia 的训练语料 The Pile 含少量中文，部分缓解了问题。Qwen 151k 中英双语词表是唯一可行的选项（-25%）。

3. **简单结构在双语 tokenizer 下已持平**。`while`、`return` 在 Qwen 下中英文 token 数相等。变量赋值在 Pythia 下也不弱。结构越简单，tokenizer 差异影响越小。

4. **LLM 时代的语言设计必须 tokenizer-语言协同**。中文 DSL 只有搭配中文 tokenizer 才有竞争力。语法优化不能弥补 tokenizer 不匹配。

> **LLM 时代的语言效率不是语言本身的属性，而是语言、Tokenizer 和训练分布共同决定的属性。** 同样的中文 DSL 语法，在 GPT-2 tokenizer 下贵 88%，在 Qwen tokenizer 下仅贵 25%——语法没变，变的是 tokenizer 是否认识这些中文字。传统编程语言时代"语法决定效率"的假设在 LLM 时代不再成立。

## 可复现

```bash
pip install tiktoken transformers
python research/tokenizer_dsl/token_bench.py     # 2-model
python research/tokenizer_dsl/multi_bench.py     # 4-model
python research/tokenizer_dsl/word_decomp.py     # 逐词切分
```

---

# Tokenizer-Language Alignment Experiment

> Does tokenizer vocabulary design determine the viability of a Chinese DSL for LLM code generation?

## Method

11 equivalent code snippets in two syntaxes (Chinese DSL vs Python), tokenized across 4 local models (≤0.5B, no API required).

## Results

| Tokenizer | Vocab | CN avg | PY avg | Gap |
|-----------|-------|--------|--------|-----|
| GPT-2 124M (OpenAI) | 50,257 | 30.5 tk | 16.3 tk | -88% |
| OPT-125M (Meta) | 50,265 | 31.5 tk | 17.3 tk | -83% |
| Pythia-160M (Eleuther) | 50,254 | 21.2 tk | 14.0 tk | -51% |
| Qwen2.5-0.5B (Alibaba) | 151,643 | 16.6 tk | 13.3 tk | -25% |

Per-word analysis: GPT-2 splits each Chinese character into 2-3 byte-fragment tokens (e.g., `循环` = 5 tokens), while Qwen encodes most Chinese keywords as single tokens. All ~50k English-optimized vocab tokenizers severely penalize Chinese DSL. Only Qwen's 151k bilingual vocabulary brings the gap down to -25%, with simple constructs (while, return) reaching parity.

## Key Findings

1. **English-optimized tokenizers are a hard bottleneck for Chinese DSL.** 83-88% token penalty is not a syntax problem — the tokenizer simply does not recognize Chinese characters.
2. **Chinese token coverage matters more than vocab size.** All three ~50k tokenizers differ by 37% (Pythia -51% vs GPT-2 -88%) due to training data composition.
3. **Simple constructs reach parity with bilingual tokenizers.** `while`, `return` show 0% gap under Qwen.
4. **LLM-era language design = tokenizer-language co-design.** Syntax optimization cannot compensate for tokenizer mismatch.

> **Language efficiency in the LLM era is not an intrinsic property of the language, but a joint property of the language, the tokenizer, and the training distribution.** The same Chinese DSL syntax costs 88% more under GPT-2's tokenizer but only 25% more under Qwen's — the syntax did not change, but the tokenizer's recognition of Chinese characters did. The traditional assumption that "syntax determines efficiency" no longer holds in the LLM era.
