# Quick Start — 5 Minutes to First Result

## Prerequisites

```bash
# Python 3.12+, with:
pip install torch numpy tiktoken
```

## 1. Clone & Run

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan

# Compile C kernels
gcc -shared -O2 -o csrc/transformer_c.dll csrc/transformer_c.c -lm

# Download GPT-2 124M from HF mirror (548MB, one-time)
python -c "
import os; os.environ['HF_ENDPOINT']='https://hf-mirror.com'
from huggingface_hub import hf_hub_download
hf_hub_download('openai-community/gpt2', 'pytorch_model.bin', cache_dir='csrc/gpt2')
"
```

## 2. Test Inference

```bash
python -X utf8 -c "
import torch, numpy as np, tiktoken, ctypes, collections
w = torch.load('csrc/gpt2/pytorch_model.bin', map_location='cpu', weights_only=True)
enc = tiktoken.get_encoding('gpt2')
# ... (see csrc/gpt2_engine.py for full engine)
print('GPT-2 124M loaded successfully')
"
```

Or use the pre-built engine:

```bash
python -X utf8 csrc/gpt2_engine.py
```

Output:
```
Prompt: Once upon a time
Once upon a time, your friend and I were in an alley...
```

## 3. Run Ternary Gating Benchmark

```bash
python -X utf8 csrc/gpt2_scale.py
```

Output:
```
GPT-2 124M — 1000 prompt benchmark
  三态门控: avg_len=12.2 stop=100% time=478s
  EOS-only:  avg_len=64.0 stop=0%   time=1943s
```

## 4. Run Sanyan Language Demo

```bash
python -X utf8 csrc/sanyan_run.py csrc/infer_demo.san
```

This runs actual Sanyan `.san` code that calls C kernels through FFI.

## What You Just Saw

The ternary gating caught GPT-2's repetition ("and and and...") at token ~12, while EOS-only generated 64 tokens of garbage. The UR threshold of 0.30 was the only signal needed — no complex heuristics.

## Next Steps

- [Full results](RESULTS.md) — all benchmark tables
- [Research report](docs/research/ternary_gating_report.md) — methodology and analysis
- [Qwen2.5 validation](csrc/qwen25_bench.py) — zero false positive check
- [Architecture](docs/architecture.md) — system design
