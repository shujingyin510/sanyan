#!/usr/bin/env bash
# 三言形式化验证 — CI 运行脚本
# GitHub Actions 中通过 apt-get install coq 安装
# 本地通过 Coq Platform 或 opam 安装
# 无可用的 Coq 时优雅退出（exit 0）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

install_coq() {
    case "$(uname -s)" in
        Linux)
            if command -v apt-get &>/dev/null; then
                sudo apt-get update -qq
                sudo apt-get install -y -qq coq
            elif command -v opam &>/dev/null; then
                opam install -y coq
            fi
            ;;
        Darwin)
            brew install coq 2>/dev/null || true
            ;;
        *)
            echo "[跳过] 当前平台 $(uname -s) 不支持自动安装 Coq"
            return 1
            ;;
    esac
}

# 检测 Coq
COQC=""
if command -v coqc &>/dev/null; then
    COQC="coqc"
elif command -v coqtop &>/dev/null; then
    COQC="coqc"
fi

if [ -z "$COQC" ]; then
    echo -e "${YELLOW}[提示] Coq 未安装，尝试自动安装...${NC}"
    if install_coq; then
        COQC="coqc"
    else
        echo -e "${YELLOW}[跳过] Coq 安装失败，跳过形式化验证${NC}"
        echo "[提示] 手动安装: https://coq.inria.fr/download"
        exit 0
    fi
fi

echo -e "${GREEN}[Coq] $($COQC --version 2>&1 | head -1)${NC}"

FLAGS="-R . SanyanFormal"

echo "[1/3] 编译三值逻辑模块..."
$COQC $FLAGS Trit.v

echo "[2/3] 编译 Agent 认知态映射模块..."
$COQC $FLAGS AgentMap.v

echo "[3/3] 编译标记指针编码模块..."
$COQC $FLAGS TaggedPtr.v

echo ""
echo -e "${GREEN}=== 三言形式化验证全部通过 ===${NC}"
echo "已证明定理:"
echo "  Trit.v:        5 条代数恒等式 + De Morgan + 往返性质"
echo "  AgentMap.v:    5→3 映射完备性 + 穷举传播表 + 门控安全性"
echo "  TaggedPtr.v:   装箱往返恒等 + 伪正概率上界 + _cstr 确定性"
