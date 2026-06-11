"""三言内置操作模块。

每个子模块实现一类操作：
  control_ops     — 控制流（if/loop/for/try/judge/匹配3）
  logic_ops       — 三态逻辑（and/or/not）
  comparison_ops  — 比较运算（eq/gt/lt/ne/gte/lte/ngt/nlt）
  arithmetic_ops  — 算术运算（add/sub/mul/div/mod/pow/digit）
  math_funcs_ops  — 数学函数（三角函数/对数/随机数/取整）
  math_extra_ops  — 统计（均值/中位数/方差/标准差）
  string_ops      — 字符串拼接、查找、替换、格式化
  list_ops        — 列表/数组/通用容器操作
  dict_ops        — 字典操作
  iter_ops        — Lambda/map/filter/reduce/apply
  io_ops          — 输出/输入/调试/断点
  file_ops        — 文件读写与模块导入
  type_ops        — 时间/类型判断
  iot_ops         — 传感器与执行器抽象
  json_ops        — JSON 序列化与反序列化
  package_ops     — 包管理器
  random_ops      — 随机操作
  regex_ops       — 正则表达式
  crypto_ops      — 哈希与编解码
  net_ops         — HTTP 请求
  system_ops      — 系统命令与环境变量
  time_ops        — 时间戳与计时
  unicode_ops     — URL/Unicode 编码
  concurrent_ops  — 并发与锁（并发融合/竞速/全部）
  ternary_generic_ops — 三态泛型容器（三态集/三态图/三态队列/三态栈）
  sandbox_ops     — 沙箱安全
  dispatcher      — 操作分派器
  registry        — 操作注册表
  device_registry — IoT 设备注册
"""
