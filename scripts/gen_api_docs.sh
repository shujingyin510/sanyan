#!/usr/bin/env bash
# 生成 API 参考文档
# 用法: bash scripts/gen_api_docs.sh
set -e
echo "生成 API 文档..."
python -m pdoc --html --output-dir docs/api \
    evaluator.py values.py ternary_core.py \
    ops/dispatcher.py ops/registry.py runtime.py
echo "文档已生成到 docs/api/"
