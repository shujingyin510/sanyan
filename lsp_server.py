"""三言语言服务器 (LSP) — 提供代码补全、诊断、悬停提示。

用法: python lsp_server.py  然后编辑器连接 stdio LSP。
"""
from __future__ import annotations
import json
import sys
import traceback
from typing import Any, Optional

# LSP 基础消息
_CONTENT_LENGTH_HEADER = "Content-Length: "


def _send(msg: dict) -> None:
    body = json.dumps(msg, ensure_ascii=False)
    data = body.encode("utf-8")
    header = f"{_CONTENT_LENGTH_HEADER}{len(data)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode() + data)
    sys.stdout.buffer.flush()


def _read() -> Optional[dict]:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            break
        if line.startswith(_CONTENT_LENGTH_HEADER):
            headers["content-length"] = int(line[len(_CONTENT_LENGTH_HEADER):])
    length = headers.get("content-length", 0)
    if length == 0:
        return None
    body = sys.stdin.buffer.read(length).decode("utf-8", errors="replace")
    return json.loads(body)


_CAPABILITIES = {
    "textDocumentSync": {
        "openClose": True,
        "change": {"syncKind": 1},  # Full
    },
    "completionProvider": {
        "triggerCharacters": [".", "（", "(", "："],
        "resolveProvider": False,
    },
    "hoverProvider": True,
}

# 三言关键字和内置命令
_KEYWORDS = [
    "设", "若", "再若", "否则", "循环", "遍历", "定义", "返回",
    "跳出", "继续", "尝试", "捕获", "判", "函数", "λ", "在",
    "导入", "输出", "加载", "计数", "调试", "从", "到", "导出",
    "注册设备", "对", "置", "读", "查", "等待",
]

_OPERATORS = [
    "加", "减", "乘", "除", "余", "幂", "取位",
    "大于", "小于", "等于", "不等于", "大于等于", "小于等于",
    "不大于", "不小于", "且", "或", "非", "同",
]

_MATH_FUNCS = [
    "绝对值", "最大值", "最小值", "平方根", "随机数", "随机态", "三进制",
    "正弦", "余弦", "正切", "对数", "常用对数",
    "向下取整", "向上取整", "四舍五入",
]

_CONTAINER_FUNCS = [
    "列表", "数组", "字典", "取", "置元素",
    "列表合", "表长", "字列", "组长", "数组列",
    "取键", "置键", "映射", "过滤", "归并", "应用",
    "排序", "反转", "包含", "去重", "切片", "求和", "合并",
]

_STRING_FUNCS = [
    "连接", "取长", "子串", "替换", "分割", "查找", "去空白",
    "大写", "小写", "前缀", "后缀",
]

_IO_FUNCS = [
    "读文件", "写文件", "转JSON", "解析JSON",
    "是数字", "是字符串", "字符串相等",
    "当前时间", "等待",
    "读取", "写入", "查询",
]

_ALL_KEYWORDS = (
    _KEYWORDS + _OPERATORS + _MATH_FUNCS + _CONTAINER_FUNCS
    + _STRING_FUNCS + _IO_FUNCS
)

_TRIGGER_CHARS = {"（", "(", "：", "."}

_TYPED_HOVER: dict[str, str] = {
    "设": "定义变量: `设 变量名 = 值;`",
    "若": "条件分支: `若 (条件) { ... }`",
    "再若": "否则若分支: `再若 (条件) { ... }`",
    "否则": "否则分支: `否则 { ... }`",
    "循环": "条件循环: `循环 (条件) { ... }`",
    "遍历": "遍历循环: `遍历 i 从 1 到 n { ... }`",
    "定义": "自定义命令: `定义 名 (参数) { ... }`",
    "返回": "函数内提前返回: `返回(值);`",
    "跳出": "退出当前循环: `跳出;`",
    "继续": "跳过本次循环迭代: `继续;`",
    "尝试": "异常处理: `尝试 { ... } 捕获 (变量) { ... }`",
    "捕获": "异常捕获: `尝试 { ... } 捕获 (变量) { ... }`",
    "判": "三态分支: `判 值 { 真 {...} 可能 {...} 假 {...} }`",
    "函数": "匿名函数: `函数(参数) { ... }`",
    "λ": "匿名函数简写: `λ(参数) { ... }`",
    "在": "遍历容器: `遍历 元素 在 容器 { ... }`",
    "导入": "模块隔离加载: `导入(\"路径\")`",
    "导出": "模块显式导出: `导出 名称1 名称2`",
    "输出": "打印值: `输出(表达式);`",
    "加载": "加载模块: `加载(\"文件\")`",
    "从": "遍历起点: `遍历 i 从 1 到 n`",
    "到": "遍历终点: `遍历 i 从 1 到 n`",
    "对": "上下文操作: `对 对象 { ... }`",
    "置": "设置执行器/传感器: `置 设备 = 状态;`",
    "读": "读取传感器值: `读 传感器;`",
    "查": "查询设备状态: `查 设备;`",
    "注册设备": "动态注册 IoT 设备: `注册设备 名称 为 类型`",
    "加": "加法: `a + b` 或 `加(a, b)`",
    "减": "减法: `a - b` 或 `减(a, b)`",
    "乘": "乘法: `a * b` 或 `乘(a, b)`",
    "除": "除法: `a / b` 或 `除(a, b)`",
    "正弦": "sin(x) — 三进制定点实现",
    "余弦": "cos(x) — 三进制定点实现",
    "正切": "tan(x) — 三进制定点实现",
    "平方根": "sqrt(x) — 三进制定点 Newton 法",
    "对数": "log(x, base?) — 三进制定点",
    "常用对数": "log10(x) — 三进制定点",
}


def _list_to_completion(items: list[str], kind: int = 14) -> list[dict[str, Any]]:
    return [{"label": i, "kind": kind} for i in sorted(items)]


def _do_diagnostics(uri: str, text: str) -> list[dict]:
    """简单语法检查：括号匹配 + #include 语法。"""
    diagnostics: list[dict] = []
    lines = text.split("\n")
    # 括号匹配
    stack: list[tuple[int, int]] = []  # (line, col)
    pairs = {")": "(", "）": "（", "}": "}", "｝": "｛"}
    opens = {"(", "（", "{", "｛"}
    for ln, line in enumerate(lines):
        for cn, ch in enumerate(line):
            if ch in opens:
                stack.append((ln, cn))
            elif ch in pairs:
                if stack and stack[-1][0] == ln:
                    stack.pop()
                elif stack:
                    diagnostics.append({
                        "range": {
                            "start": {"line": ln, "character": cn},
                            "end": {"line": ln, "character": cn + 1},
                        },
                        "severity": 1,
                        "message": f"不匹配的括号 '{ch}'，期望 '{pairs[ch]}'",
                    })
    for ln, cn in stack:
        diagnostics.append({
            "range": {
                "start": {"line": ln, "character": cn},
                "end": {"line": ln, "character": cn + 1},
            },
            "severity": 1,
            "message": "未闭合的括号",
        })
    return diagnostics


def _do_completion(text: str, pos: dict) -> Optional[dict]:
    """基于当前文本和位置生成补全。"""
    line = text.split("\n")[pos["line"]][:pos["character"]]
    # 空或只空格 → 所有关键字
    if not line.strip():
        return {"isIncomplete": False, "items": _list_to_completion(_ALL_KEYWORDS)}
    prefix = line.split()[-1] if line.split() else ""
    # 前缀匹配
    matches = [k for k in _ALL_KEYWORDS if k.startswith(prefix)]
    return {"isIncomplete": False, "items": _list_to_completion(matches or _ALL_KEYWORDS)}


def _do_hover(text: str, pos: dict) -> Optional[dict]:
    """悬停提示。"""
    lines = text.split("\n")
    if pos["line"] >= len(lines):
        return None
    line = lines[pos["line"]]
    col = pos["character"]
    if col >= len(line):
        return None
    # 提取当前单词
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in "_{}（）"):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in "_{}（）"):
        end += 1
    word = line[start:end]
    if word in _TYPED_HOVER:
        return {
            "contents": {
                "kind": "markdown",
                "value": f"**{word}**\n\n{_TYPED_HOVER[word]}",
            }
        }
    if word in _MATH_FUNCS:
        return {
            "contents": {
                "kind": "markdown",
                "value": f"**{word}** — 数学函数（三进制定点）",
            }
        }
    return None


def _handle_message(msg: dict) -> None:
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        _send({
            "id": msg_id,
            "result": {
                "capabilities": _CAPABILITIES,
                "serverInfo": {"name": "sanyan-lsp", "version": "0.1.0"},
            },
        })
        _send({"method": "initialized", "params": {}})
        return

    if method == "shutdown":
        _send({"id": msg_id, "result": None})
        return

    if method == "exit":
        sys.exit(0)

    if method == "textDocument/didOpen" or method == "textDocument/didChange":
        uri = params.get("textDocument", {}).get("uri", "")
        text = ""
        if method == "textDocument/didOpen":
            text = params.get("textDocument", {}).get("text", "")
        else:
            for change in params.get("contentChanges", []):
                text = change.get("text", "")
        if text:
            diagnostics = _do_diagnostics(uri, text)
            _send({
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diagnostics},
            })
        return

    if method == "textDocument/completion":
        uri = params.get("textDocument", {}).get("uri", "")
        text = _open_docs.get(uri, "")
        pos = params.get("position", {})
        result = _do_completion(text, pos)
        _send({"id": msg_id, "result": result})
        return

    if method == "textDocument/hover":
        uri = params.get("textDocument", {}).get("uri", "")
        text = _open_docs.get(uri, "")
        pos = params.get("position", {})
        result = _do_hover(text, pos)
        _send({"id": msg_id, "result": result})
        return

    # 未知方法 → 返回空
    if msg_id is not None:
        _send({"id": msg_id, "result": None})


_open_docs: dict[str, str] = {}

def main() -> None:
    while True:
        msg = _read()
        if msg is None:
            break
        # 跟踪打开的文档
        params = msg.get("params", {})
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        if msg.get("method") == "textDocument/didOpen":
            _open_docs[uri] = td.get("text", "")
        elif msg.get("method") == "textDocument/didChange":
            for change in params.get("contentChanges", []):
                _open_docs[uri] = change.get("text", "")
        elif msg.get("method") == "textDocument/didClose":
            _open_docs.pop(uri, None)

        try:
            _handle_message(msg)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    main()
