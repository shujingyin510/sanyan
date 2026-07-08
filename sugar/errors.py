"""错误收集与报告"""

from __future__ import annotations

from core.values import SanyanSyntaxError


class SugarError:
    def __init__(self, line: int, col: int, message: str) -> None:
        self.line = line
        self.col = col
        self.message = message

    def __str__(self) -> str:
        return f'行 {self.line}: {self.message}'


class SugarErrorReporter:
    def __init__(self, source: str = '') -> None:
        self.source = source
        self.errors: list[SugarError] = []
        self._lines: list[str] | None = None

    def error(self, line: int, col: int, message: str) -> None:
        self.errors.append(SugarError(line, col, message))

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def report(self) -> str:
        if not self.errors:
            return ''
        lines = []
        for e in self.errors:
            lines.append(str(e))
            if self.source:
                src_line = self._get_line(e.line)
                if src_line:
                    lines.append(f'  | {src_line}')
                    lines.append(f'  | {" " * (e.col - 1)}^')
        return '\n'.join(lines)

    def _get_line(self, line_num: int) -> str:
        if self._lines is None:
            self._lines = self.source.split('\n')
        if 1 <= line_num <= len(self._lines):
            return self._lines[line_num - 1]
        return ''

    def raise_if_any(self) -> None:
        # 抛 SanyanSyntaxError（继承 Python SyntaxError，反向兼容既有 catch SyntaxError
        # 的调用点）——统一进 SanyanError 家族，糖语法的语法错误不再从 catch SanyanError
        # 漏网（对抗探针 0708：此前裸 SyntaxError 与 S 表达式前端不一致）。
        if self.errors:
            raise SanyanSyntaxError(str(self.errors[0]))
