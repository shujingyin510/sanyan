# 三言 Sanyan — 运行时镜像
# 构建： docker build -t sanyan .
# 运行： docker run -it --rm sanyan            # 进入 REPL
#        docker run --rm -v "$PWD:/work" -w /work sanyan run demo.san
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sanyan" \
      org.opencontainers.image.description="内置三态逻辑（真/假/可能）的中文编程语言" \
      org.opencontainers.image.source="https://github.com/shujingyin510/sanyan" \
      org.opencontainers.image.licenses="GPL-3.0-only"

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# 语言核心零第三方依赖；.[cli] 仅额外装 rich 让 CLI 终端渲染可用
# （需 LLVM 原生编译请自行改成 .[all]，会额外拉 llvmlite）
RUN pip install --no-cache-dir .[cli]

ENTRYPOINT ["sanyan"]
CMD ["repl"]
