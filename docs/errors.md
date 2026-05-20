# 三言 v3.12.0 错误信息说明

所有运行阶段错误均继承自 `SanyanError`，可被 `尝试/捕获` 捕获：

| 错误类型 | 含义 | 常见原因 |
|----------|------|----------|
| `SanyanNameError` | 未定义的符号/操作 | 变量名拼写错误或未引入 |
| `SanyanSyntaxError` | 参数个数/格式错误 | 内置函数参数不匹配 |
| `SanyanTypeError` | 类型错误 | 参数类型不匹配 |
| `SanyanValueError` | 值错误 | 除数零、负开方、无效输入等 |
| `SanyanRuntimeError` | 运行时错误 | 递归超深、执行中断等 |
| `SanyanKeyError` | 键错误 | 字典中访问不存在的键 |
| `SanyanAttributeError` | 属性错误 | 对非容器做点号访问 |
| `SanyanIOError` | 文件/IO 错误 | 文件读取、写入、加载失败 |
| `ReturnException` | 函数返回（内部控制流） | 由 `返回` 关键字触发 |
| `BreakException` / `ContinueException` | 循环中断（内部控制流） | 由 `跳出`/`继续` 关键字触发 |
