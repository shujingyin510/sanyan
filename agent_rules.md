# Agent Rules — 工具链规则库

规则由 LLM 生成，用户审批后生效。执行时按规则走，不调 LLM 选工具。

格式：
```
## 规则：{名称}
匹配：{正则表达式}
工具链：
1. {工具名}({参数说明}) — {描述}
2. {工具名}({参数说明}) — {描述}
...
验证：{验证命令}
```

---

## 规则：创建Python模块
匹配：新增|创建.*\.py|写.*函数|实现.*模块|写.*模块
工具链：
1. write_file({filename}|{code}) — 创建文件
2. write_file({test_file}|{test_code}) — 创建测试文件
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：创建Python类
匹配：创建.*类|定义.*class|新增.*类|写.*类
工具链：
1. write_file({filename}|{code}) — 创建文件
2. write_file({test_file}|{test_code}) — 创建测试文件
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：创建Python包
匹配：创建.*包|新增.*package|新建.*目录.*模块
工具链：
1. run_shell(mkdir -p {package_dir}) — 创建目录
2. write_file({package_dir}/__init__.py|{init_code}) — 创建__init__.py
3. write_file({package_dir}/{module}.py|{code}) — 创建模块
4. write_file(tests/test_{module}.py|{test_code}) — 创建测试
5. run_shell(python -X utf8 -m pytest tests/test_{module}.py -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/test_{module}.py -x -q

## 规则：修复导入错误
匹配：ImportError|ModuleNotFoundError|导入.*错误|找不到.*模块
工具链：
1. read_file({file}) — 读取文件
2. search_code(import|from) — 搜索导入语句
3. replace_in_file({file}|{old_import}|{new_import}) — 修复导入
4. run_shell(python -X utf8 -c "import {module}") — 验证导入
验证：python -X utf8 -c "import {module}"

## 规则：修复类型错误
匹配：TypeError|类型.*错误|参数.*类型|返回.*类型
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复类型
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复语法错误
匹配：SyntaxError|语法.*错误|缩进.*错误|IndentationError
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code}) — 修复语法
3. run_shell(python -X utf8 -m py_compile {file}) — 验证语法
验证：python -X utf8 -m py_compile {file}

## 规则：修复运行时错误
匹配：RuntimeError|运行时.*错误|异常|Exception|Traceback
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复代码
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复逻辑错误
匹配：逻辑.*错误|结果.*不对|输出.*错误|计算.*错误
工具链：
1. read_file({file}) — 读取文件
2. search_code({function_name}) — 搜索函数
3. replace_in_file({file}|{old_logic}|{new_logic}) — 修复逻辑
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构函数
匹配：重构.*函数|提取.*函数|拆分.*函数|合并.*函数|重构.*代码
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_function}|{new_function}) — 重构函数
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构类
匹配：重构.*类|提取.*类|拆分.*类|合并.*类
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_class}|{new_class}) — 重构类
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构模块
匹配：重构.*模块|拆分.*模块|合并.*模块|整理.*模块
工具链：
1. analyze({file}) — 分析模块结构
2. read_file({file}) — 读取模块
3. write_file({new_module}.py|{new_code}) — 创建新模块
4. replace_in_file({file}|{old_import}|{new_import}) — 更新导入
5. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加单元测试
匹配：添加.*单元测试|写.*unit.*test|补充.*测试|写测试|添加测试|测试.*覆盖
工具链：
1. read_file({source_file}) — 读取被测代码
2. write_file({test_file}|{test_code}) — 创建测试文件
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加集成测试
匹配：添加.*集成测试|写.*integration.*test|端到端.*测试
工具链：
1. read_file({source_files}) — 读取相关代码
2. write_file({test_file}|{test_code}) — 创建测试文件
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加参数化测试
匹配：参数化.*测试|parametrize|多.*测试用例
工具链：
1. read_file({source_file}) — 读取被测代码
2. write_file({test_file}|{test_code}) — 创建参数化测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加异常测试
匹配：异常.*测试|测试.*异常|测试.*错误|test.*exception
工具链：
1. read_file({source_file}) — 读取被测代码
2. write_file({test_file}|{test_code}) — 创建异常测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：更新README
匹配：更新.*README|修改.*README|README.*文档
工具链：
1. read_file(README.md) — 读取README
2. replace_in_file(README.md|{old_content}|{new_content}) — 更新内容
验证：echo done

## 规则：更新CHANGELOG
匹配：更新.*CHANGELOG|修改.*CHANGELOG|CHANGELOG.*文档
工具链：
1. read_file(CHANGELOG.md) — 读取CHANGELOG
2. replace_in_file(CHANGELOG.md|{old_content}|{new_content}) — 更新内容
验证：echo done

## 规则：添加注释
匹配：添加.*注释|补充.*注释|注释.*代码|写.*注释
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_comments}) — 添加注释
验证：echo done

## 规则：添加类型注解
匹配：添加.*类型.*注解|type.*hint|类型.*标注
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_types}) — 添加类型注解
3. run_shell(mypy {file}) — 验证类型
验证：mypy {file}

## 规则：添加日志
匹配：添加.*日志|添加.*logging|日志.*记录
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_logging}) — 添加日志
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加错误处理
匹配：添加.*错误处理|添加.*异常处理|try.*except|error.*handling
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_try_except}) — 添加错误处理
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加输入验证
匹配：添加.*输入验证|参数.*校验|validate.*input
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_validation}) — 添加输入验证
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加配置文件
匹配：添加.*配置|创建.*config|新建.*settings|配置.*文件
工具链：
1. write_file({config_file}|{config_content}) — 创建配置文件
2. write_file({config_example}|{example_content}) — 创建示例配置
验证：echo done

## 规则：添加CLI参数
匹配：添加.*CLI.*参数|命令行.*参数|argparse|click
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_args}) — 添加CLI参数
3. run_shell(python {file} --help) — 验证帮助信息
验证：python {file} --help

## 规则：添加环境变量
匹配：添加.*环境变量|env.*variable|os\.environ
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_env}) — 添加环境变量
3. write_file(.env.example|{env_example}) — 创建示例环境文件
验证：echo done

## 规则：添加依赖
匹配：添加.*依赖|安装.*包|pip.*install|requirements
工具链：
1. read_file(requirements.txt) — 读取依赖文件
2. replace_in_file(requirements.txt|{old_deps}|{new_deps}) — 添加依赖
3. run_shell(pip install -r requirements.txt) — 安装依赖
验证：pip install -r requirements.txt

## 规则：添加Git忽略
匹配：添加.*gitignore|git.*忽略|忽略.*文件
工具链：
1. read_file(.gitignore) — 读取gitignore
2. replace_in_file(.gitignore|{old_patterns}|{new_patterns}) — 添加忽略规则
验证：echo done

## 规则：添加Makefile
匹配：添加.*Makefile|创建.*make|make.*命令
工具链：
1. write_file(Makefile|{makefile_content}) — 创建Makefile
2. run_shell(make help) — 验证帮助信息
验证：make help

## 规则：添加Docker配置
匹配：添加.*Docker|创建.*Dockerfile|docker.*配置
工具链：
1. write_file(Dockerfile|{dockerfile_content}) — 创建Dockerfile
2. write_file(docker-compose.yml|{compose_content}) — 创建compose文件
3. write_file(.dockerignore|{dockerignore_content}) — 创建dockerignore
验证：echo done

## 规则：添加CI配置
匹配：添加.*CI|GitHub.*Actions|持续集成|自动化.*测试
工具链：
1. run_shell(mkdir -p .github/workflows) — 创建目录
2. write_file(.github/workflows/test.yml|{workflow_content}) — 创建workflow
验证：echo done

## 规则：代码格式化
匹配：格式化.*代码|format.*code|ruff.*format|black
工具链：
1. run_shell(ruff format {file}) — 格式化代码
2. run_shell(ruff check {file}) — 检查代码
验证：ruff check {file}

## 规则：代码检查
匹配：代码.*检查|lint.*code|ruff.*check|pylint|flake8
工具链：
1. run_shell(ruff check {file}) — 检查代码
2. run_shell(ruff check --fix {file}) — 自动修复
验证：ruff check {file}

## 规则：类型检查
匹配：类型.*检查|type.*check|mypy|类型.*验证
工具链：
1. run_shell(mypy {file}) — 类型检查
验证：mypy {file}

## 规则：性能分析
匹配：性能.*分析|profile|性能.*测试|benchmark
工具链：
1. read_file({file}) — 读取代码
2. run_shell(python -m cProfile -s cumulative {file}) — 性能分析
验证：echo done

## 规则：内存分析
匹配：内存.*分析|memory.*profile|内存.*泄漏
工具链：
1. read_file({file}) — 读取代码
2. run_shell(python -m memory_profiler {file}) — 内存分析
验证：echo done

## 规则：添加文档字符串
匹配：添加.*docstring|文档.*字符串|函数.*说明
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_docstring}) — 添加文档字符串
验证：echo done

## 规则：添加类型提示
匹配：添加.*类型提示|type.*hint|typing|类型.*标注
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_hints}) — 添加类型提示
3. run_shell(mypy {file}) — 验证类型
验证：mypy {file}

## 规则：添加数据类
匹配：添加.*数据类|dataclass|数据.*结构
工具链：
1. write_file({filename}|{code}) — 创建数据类
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加枚举类
匹配：添加.*枚举|enum|枚举.*类
工具链：
1. write_file({filename}|{code}) — 创建枚举类
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加抽象类
匹配：添加.*抽象.*类|abstract|ABC|接口.*类
工具链：
1. write_file({filename}|{code}) — 创建抽象类
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加装饰器
匹配：添加.*装饰器|decorator|包装.*函数
工具链：
1. write_file({filename}|{code}) — 创建装饰器
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加上下文管理器
匹配：添加.*上下文.*管理器|context.*manager|with.*语句
工具链：
1. write_file({filename}|{code}) — 创建上下文管理器
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加迭代器
匹配：添加.*迭代器|iterator|生成器|generator
工具链：
1. write_file({filename}|{code}) — 创建迭代器
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加缓存
匹配：添加.*缓存|cache|lru_cache|记忆化
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_cache}) — 添加缓存
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加并发
匹配：添加.*并发|多线程|multiprocessing|asyncio|并发.*执行
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_concurrency}) — 添加并发
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加序列化
匹配：添加.*序列化|serialize|json.*转换|pickle|marshal
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_serialization}) — 添加序列化
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据库操作
匹配：添加.*数据库|创建.*数据库|database|SQL|sqlite|mysql|postgresql
工具链：
1. write_file({filename}|{code}) — 创建数据库模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加API端点
匹配：添加.*API|创建.*端点|REST.*API|Flask.*路由|FastAPI
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_endpoint}) — 添加API端点
3. write_file({test_file}|{test_code}) — 创建测试
4. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加中间件
匹配：添加.*中间件|middleware|拦截器|interceptor
工具链：
1. write_file({filename}|{code}) — 创建中间件
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加认证
匹配：添加.*认证|authentication|登录|JWT|token
工具链：
1. write_file({filename}|{code}) — 创建认证模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加授权
匹配：添加.*授权|authorization|权限|permission|role
工具链：
1. write_file({filename}|{code}) — 创建授权模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加加密
匹配：添加.*加密|encrypt|decrypt|hash.*密码|密码.*哈希
工具链：
1. write_file({filename}|{code}) — 创建加密模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加压缩
匹配：添加.*压缩|compress|decompress|zip|gzip
工具链：
1. write_file({filename}|{code}) — 创建压缩模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加网络请求
匹配：添加.*网络.*请求|HTTP.*请求|requests|urllib|httpx
工具链：
1. write_file({filename}|{code}) — 创建网络模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加文件操作
匹配：添加.*文件.*操作|读写.*文件|文件.*处理|IO.*操作
工具链：
1. write_file({filename}|{code}) — 创建文件操作模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加数据处理
匹配：添加.*数据.*处理|数据.*转换|数据.*清洗|ETL
工具链：
1. write_file({filename}|{code}) — 创建数据处理模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加字符串处理
匹配：添加.*字符串.*处理|字符串.*操作|文本.*处理|string.*utils
工具链：
1. write_file({filename}|{code}) — 创建字符串处理模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加日期时间处理
匹配：添加.*日期.*时间|datetime|时间.*处理|日期.*操作
工具链：
1. write_file({filename}|{code}) — 创建日期时间模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加数学计算
匹配：添加.*数学.*计算|数学.*函数|math.*utils|计算.*模块
工具链：
1. write_file({filename}|{code}) — 创建数学模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加正则表达式
匹配：添加.*正则.*表达式|regex|re\.|pattern.*match
工具链：
1. write_file({filename}|{code}) — 创建正则模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加日志记录
匹配：添加.*日志.*记录|logging|日志.*系统|log.*handler
工具链：
1. write_file({filename}|{code}) — 创建日志模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加配置管理
匹配：添加.*配置.*管理|config.*manager|设置.*管理|settings
工具链：
1. write_file({filename}|{code}) — 创建配置管理模块
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加插件系统
匹配：添加.*插件.*系统|plugin|扩展.*机制|hook
工具链：
1. write_file({filename}|{code}) — 创建插件系统
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加事件系统
匹配：添加.*事件.*系统|event|事件.*驱动|observer|订阅.*发布
工具链：
1. write_file({filename}|{code}) — 创建事件系统
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加状态机
匹配：添加.*状态机|state.*machine|有限.*状态|FSM
工具链：
1. write_file({filename}|{code}) — 创建状态机
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加命令模式
匹配：添加.*命令.*模式|command.*pattern|命令.*处理器|handler
工具链：
1. write_file({filename}|{code}) — 创建命令模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加策略模式
匹配：添加.*策略.*模式|strategy.*pattern|策略.*类|算法.*切换
工具链：
1. write_file({filename}|{code}) — 创建策略模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加工厂模式
匹配：添加.*工厂.*模式|factory.*pattern|工厂.*类|创建.*对象
工具链：
1. write_file({filename}|{code}) — 创建工厂模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加单例模式
匹配：添加.*单例.*模式|singleton.*pattern|单例.*类|全局.*实例
工具链：
1. write_file({filename}|{code}) — 创建单例模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加观察者模式
匹配：添加.*观察者.*模式|observer.*pattern|观察者.*类|监听.*器
工具链：
1. write_file({filename}|{code}) — 创建观察者模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加适配器模式
匹配：添加.*适配器.*模式|adapter.*pattern|适配器.*类|接口.*转换
工具链：
1. write_file({filename}|{code}) — 创建适配器模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加装饰器模式
匹配：添加.*装饰器.*模式|decorator.*pattern|装饰器.*类|包装.*类
工具链：
1. write_file({filename}|{code}) — 创建装饰器模式
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

---

# 反模式规则 — 防止过度工程

## 规则：禁止过度工程
匹配：.*
约束：
- 不创建只有一个方法的类，直接用函数
- 不引入新依赖除非任务明确要求
- 不添加抽象层除非有 3 个以上使用场景
- 不重构不在任务范围内的代码
- 不添加配置文件除非任务明确要求
- 不添加日志/监控除非任务明确要求
- 不添加中间件/插件系统除非任务明确要求

## 规则：遵循项目风格
匹配：.*
约束：
- 执行前查 learned_styles.md 了解项目风格
- 如果项目用函数就用函数，不要改成类
- 如果项目没有类型注解就不要强制添加
- 如果项目没有日志就不要添加日志
- 遵循现有的代码组织方式

## 规则：最小变更原则
匹配：.*
约束：
- 只修改任务要求的代码
- 不要"顺便"修复其他问题
- 不要重构不在任务范围内的代码
- 不要添加额外的功能
- 不要修改测试除非任务要求

## 规则：代码量自检
匹配：.*
约束：
- 单个函数不超过 50 行
- 单个文件不超过 500 行
- 超过时考虑拆分，但不要过度拆分
- 一个功能一个文件，不要把所有东西放一起

## 规则：依赖管理
匹配：.*
约束：
- 不添加 requirements.txt 中没有的依赖
- 不导入项目中没有用过的库
- 优先使用标准库
- 需要新依赖时明确告知用户

---

# 扩充规则 — 更多场景覆盖

## 规则：修复索引错误
匹配：IndexError|索引.*错误|下标.*越界|list.*index
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复索引
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复键错误
匹配：KeyError|键.*错误|字典.*没有|key.*not.*found
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复键错误
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复属性错误
匹配：AttributeError|属性.*错误|没有.*属性|object.*has.*no.*attribute
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复属性错误
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复值错误
匹配：ValueError|值.*错误|无效.*值|invalid.*value
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复值错误
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复文件错误
匹配：FileNotFoundError|文件.*不存在|找不到.*文件|No such file
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复文件路径
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复权限错误
匹配：PermissionError|权限.*错误|Permission denied|访问.*拒绝
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复权限
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复编码错误
匹配：UnicodeDecodeError|UnicodeEncodeError|编码.*错误|codec
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复编码
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复递归错误
匹配：RecursionError|递归.*错误|maximum.*recursion|栈溢出
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复递归
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复内存错误
匹配：MemoryError|内存.*错误|内存.*不足|Out of memory
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 优化内存
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：修复超时错误
匹配：TimeoutError|超时.*错误|timeout|timed.*out
工具链：
1. read_file({file}) — 读取文件
2. search_code({error_keyword}) — 搜索错误位置
3. replace_in_file({file}|{old_code}|{new_code}) — 修复超时
4. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证修复
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构提取常量
匹配：提取.*常量|magic.*number|硬编码|常量.*定义
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_value}|{constant_name}) — 提取常量
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构提取变量
匹配：提取.*变量|临时.*变量|变量.*命名|可读性
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_var}) — 提取变量
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构简化条件
匹配：简化.*条件|嵌套.*if|条件.*复杂|简化.*逻辑
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_condition}|{new_condition}) — 简化条件
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构消除重复
匹配：消除.*重复|代码.*重复|DRY|重复.*代码
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{duplicate_code}|{shared_function}) — 消除重复
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构早返回
匹配：早返回|guard.*clause|提前.*返回|减少.*嵌套
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{nested_code}|{early_return}) — 早返回
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：重构循环优化
匹配：优化.*循环|循环.*性能|列表.*推导|生成器
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_loop}|{new_loop}) — 优化循环
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加边界检查
匹配：添加.*边界.*检查|边界.*条件|edge.*case|空.*检查
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_check}) — 添加边界检查
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加空值检查
匹配：添加.*空值.*检查|None.*检查|null.*检查|空.*判断
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_check}) — 添加空值检查
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加类型转换
匹配：类型.*转换|类型.*强转|cast|类型.*转换.*错误
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_cast}) — 添加类型转换
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加默认值
匹配：添加.*默认.*值|default.*value|参数.*默认|可选.*参数
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_default}) — 添加默认值
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加重试机制
匹配：添加.*重试|retry|失败.*重试|重试.*机制
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_retry}) — 添加重试
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加超时控制
匹配：添加.*超时|timeout|超时.*控制|超时.*处理
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_timeout}) — 添加超时
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加进度显示
匹配：添加.*进度|progress|进度.*条|进度.*显示
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_progress}) — 添加进度
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加结果缓存
匹配：添加.*结果.*缓存|cache.*result|缓存.*结果|结果.*复用
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_cache}) — 添加缓存
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加批量处理
匹配：添加.*批量|batch|批量.*处理|批量.*操作
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_batch}) — 添加批量
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加异步处理
匹配：添加.*异步|async|await|异步.*处理|协程
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_async}) — 添加异步
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加上下文管理
匹配：添加.*上下文.*管理|with.*语句|context.*manager|资源.*释放
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_context}) — 添加上下文
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加信号处理
匹配：添加.*信号.*处理|signal|中断.*处理|优雅.*退出
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_signal}) — 添加信号处理
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加配置验证
匹配：添加.*配置.*验证|validate.*config|配置.*检查|配置.*校验
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_validation}) — 添加配置验证
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加健康检查
匹配：添加.*健康.*检查|health.*check|健康.*接口|存活.*探针
工具链：
1. write_file({filename}|{code}) — 创建健康检查
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加指标收集
匹配：添加.*指标.*收集|metrics|指标.*接口|监控.*指标
工具链：
1. write_file({filename}|{code}) — 创建指标收集
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加限流控制
匹配：添加.*限流|rate.*limit|限流.*控制|请求.*限制
工具链：
1. write_file({filename}|{code}) — 创建限流控制
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加熔断机制
匹配：添加.*熔断|circuit.*breaker|熔断.*机制|降级.*处理
工具链：
1. write_file({filename}|{code}) — 创建熔断机制
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加配置热更新
匹配：添加.*配置.*热更新|hot.*reload|配置.*动态|配置.*刷新
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_reload}) — 添加热更新
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据验证
匹配：添加.*数据.*验证|validate.*data|数据.*校验|数据.*检查
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_validation}) — 添加数据验证
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据转换
匹配：添加.*数据.*转换|convert.*data|数据.*转换|格式.*转换
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_convert}) — 添加数据转换
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据过滤
匹配：添加.*数据.*过滤|filter.*data|数据.*筛选|数据.*过滤
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_filter}) — 添加数据过滤
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据排序
匹配：添加.*数据.*排序|sort.*data|数据.*排列|排序.*规则
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_sort}) — 添加数据排序
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据聚合
匹配：添加.*数据.*聚合|aggregate|数据.*汇总|分组.*统计
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_aggregate}) — 添加数据聚合
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据导出
匹配：添加.*数据.*导出|export.*data|导出.*文件|导出.*格式
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_export}) — 添加数据导出
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据导入
匹配：添加.*数据.*导入|import.*data|导入.*文件|导入.*格式
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_import}) — 添加数据导入
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据备份
匹配：添加.*数据.*备份|backup|备份.*数据|数据.*恢复
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_backup}) — 添加数据备份
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加数据清理
匹配：添加.*数据.*清理|cleanup|清理.*数据|数据.*清理
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_cleanup}) — 添加数据清理
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加版本管理
匹配：添加.*版本.*管理|version|版本.*号|版本.*控制
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_version}) — 添加版本管理
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加迁移脚本
匹配：添加.*迁移.*脚本|migrate|数据库.*迁移|数据.*迁移
工具链：
1. write_file({filename}|{code}) — 创建迁移脚本
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加种子数据
匹配：添加.*种子.*数据|seed|初始.*数据|测试.*数据
工具链：
1. write_file({filename}|{code}) — 创建种子数据
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加数据校验
匹配：添加.*数据.*校验|schema.*验证|数据.*格式.*校验|JSON.*验证
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_schema}) — 添加数据校验
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加API文档
匹配：添加.*API.*文档|swagger|openapi|API.*说明
工具链：
1. write_file({filename}|{code}) — 创建API文档
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：echo done

## 规则：添加CHANGELOG
匹配：添加.*CHANGELOG|更新.*CHANGELOG|CHANGELOG.*条目|版本.*记录
工具链：
1. read_file(CHANGELOG.md) — 读取CHANGELOG
2. replace_in_file(CHANGELOG.md|{old_content}|{new_content}) — 添加条目
验证：echo done

## 规则：添加发布脚本
匹配：添加.*发布.*脚本|release|发布.*流程|版本.*发布
工具链：
1. write_file({filename}|{code}) — 创建发布脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：echo done

## 规则：添加部署脚本
匹配：添加.*部署.*脚本|deploy|部署.*流程|自动.*部署
工具链：
1. write_file({filename}|{code}) — 创建部署脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：echo done

## 规则：添加监控脚本
匹配：添加.*监控.*脚本|monitor|监控.*告警|告警.*脚本
工具链：
1. write_file({filename}|{code}) — 创建监控脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：echo done

## 规则：添加日志轮转
匹配：添加.*日志.*轮转|log.*rotation|日志.*切割|日志.*归档
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_rotation}) — 添加日志轮转
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加日志级别
匹配：添加.*日志.*级别|log.*level|日志.*过滤|日志.*配置
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_level}) — 添加日志级别
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加日志格式
匹配：添加.*日志.*格式|log.*format|日志.*样式|日志.*模板
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_format}) — 添加日志格式
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 验证功能不变
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加日志收集
匹配：添加.*日志.*收集|log.*collect|日志.*聚合|日志.*中心
工具链：
1. write_file({filename}|{code}) — 创建日志收集
2. write_file({test_file}|{test_code}) — 创建测试
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加性能测试
匹配：添加.*性能.*测试|benchmark|性能.*基准|性能.*测试
工具链：
1. write_file({filename}|{code}) — 创建性能测试
2. run_shell(python {filename}) — 运行性能测试
验证：echo done

## 规则：添加压力测试
匹配：添加.*压力.*测试|stress.*test|负载.*测试|并发.*测试
工具链：
1. write_file({filename}|{code}) — 创建压力测试
2. run_shell(python {filename}) — 运行压力测试
验证：echo done

## 规则：添加模糊测试
匹配：添加.*模糊.*测试|fuzz.*test|随机.*测试|模糊.*测试
工具链：
1. write_file({filename}|{code}) — 创建模糊测试
2. run_shell(python {filename}) — 运行模糊测试
验证：echo done

## 规则：添加快照测试
匹配：添加.*快照.*测试|snapshot|快照.*对比|快照.*验证
工具链：
1. write_file({filename}|{code}) — 创建快照测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加属性测试
匹配：添加.*属性.*测试|property.*test|hypothesis|属性.*验证
工具链：
1. write_file({filename}|{code}) — 创建属性测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加变异测试
匹配：添加.*变异.*测试|mutation.*test|变异.*验证|变异.*测试
工具链：
1. write_file({filename}|{code}) — 创建变异测试
2. run_shell(python {filename}) — 运行变异测试
验证：echo done

## 规则：添加契约测试
匹配：添加.*契约.*测试|contract.*test|接口.*契约|契约.*验证
工具链：
1. write_file({filename}|{code}) — 创建契约测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加回归测试
匹配：添加.*回归.*测试|regression.*test|回归.*验证|回归.*测试
工具链：
1. write_file({filename}|{code}) — 创建回归测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加冒烟测试
匹配：添加.*冒烟.*测试|smoke.*test|冒烟.*验证|冒烟.*测试
工具链：
1. write_file({filename}|{code}) — 创建冒烟测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加端到端测试
匹配：添加.*端到端.*测试|e2e.*test|端到端.*验证|端到端.*测试
工具链：
1. write_file({filename}|{code}) — 创建端到端测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加验收测试
匹配：添加.*验收.*测试|acceptance.*test|验收.*验证|验收.*测试
工具链：
1. write_file({filename}|{code}) — 创建验收测试
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试夹具
匹配：添加.*测试.*夹具|fixture|测试.*准备|测试.*清理
工具链：
1. write_file({filename}|{code}) — 创建测试夹具
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试标记
匹配：添加.*测试.*标记|mark|测试.*分组|测试.*分类
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_mark}) — 添加测试标记
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试覆盖
匹配：添加.*测试.*覆盖|coverage|测试.*覆盖率|覆盖.*报告
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} tests/) — 运行覆盖率测试
2. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=html tests/) — 生成报告
验证：echo done

## 规则：添加测试并行
匹配：添加.*测试.*并行|parallel.*test|并行.*测试|测试.*加速
工具链：
1. run_shell(python -X utf8 -m pytest -n auto tests/) — 并行运行测试
验证：python -X utf8 -m pytest -n auto tests/

## 规则：添加测试重试
匹配：添加.*测试.*重试|retry.*test|失败.*重试|测试.*重跑
工具链：
1. run_shell(python -X utf8 -m pytest --reruns=3 tests/) — 重试运行测试
验证：python -X utf8 -m pytest --reruns=3 tests/

## 规则：添加测试超时
匹配：添加.*测试.*超时|timeout.*test|测试.*超时|超时.*测试
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_timeout}) — 添加测试超时
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试随机
匹配：添加.*测试.*随机|random.*test|随机.*顺序|测试.*随机化
工具链：
1. run_shell(python -X utf8 -m pytest --randomly-seed=1234 tests/) — 随机运行测试
验证：python -X utf8 -m pytest --randomly-seed=1234 tests/

## 规则：添加测试报告
匹配：添加.*测试.*报告|report.*test|测试.*结果|测试.*输出
工具链：
1. run_shell(python -X utf8 -m pytest --html=report.html tests/) — 生成HTML报告
验证：echo done

## 规则：添加测试标签
匹配：添加.*测试.*标签|tag.*test|测试.*分类|测试.*标签
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_tag}) — 添加测试标签
3. run_shell(python -X utf8 -m pytest -m {tag} tests/) — 运行标记测试
验证：python -X utf8 -m pytest -m {tag} tests/

## 规则：添加测试跳过
匹配：添加.*测试.*跳过|skip.*test|跳过.*测试|测试.*跳过
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_skip}) — 添加测试跳过
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试预期失败
匹配：添加.*测试.*预期.*失败|xfail|预期.*失败|测试.*失败
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_xfail}) — 添加预期失败
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试参数化
匹配：添加.*测试.*参数化|parametrize|参数化.*测试|测试.*参数
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_parametrize}) — 添加参数化
3. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试夹具共享
匹配：添加.*测试.*夹具.*共享|conftest|共享.*夹具|夹具.*共享
工具链：
1. write_file(conftest.py|{code}) — 创建conftest
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试环境
匹配：添加.*测试.*环境|test.*env|测试.*配置|环境.*配置
工具链：
1. write_file({filename}|{code}) — 创建测试环境
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试数据
匹配：添加.*测试.*数据|test.*data|测试.*数据|数据.*测试
工具链：
1. write_file({filename}|{code}) — 创建测试数据
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试清理
匹配：添加.*测试.*清理|teardown|测试.*清理|清理.*测试
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_teardown}) — 添加测试清理
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试隔离
匹配：添加.*测试.*隔离|isolation|测试.*独立|隔离.*测试
工具链：
1. read_file({file}) — 读取文件
2. replace_in_file({file}|{old_code}|{new_code_with_isolation}) — 添加测试隔离
3. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试快照
匹配：添加.*测试.*快照|snapshot.*test|快照.*测试|测试.*快照
工具链：
1. write_file({filename}|{code}) — 创建测试快照
2. run_shell(python -X utf8 -m pytest {test_file} -x -q) — 运行测试
验证：python -X utf8 -m pytest {test_file} -x -q

## 规则：添加测试覆盖率报告
匹配：添加.*测试.*覆盖率.*报告|coverage.*report|覆盖率.*报告|报告.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=html tests/) — 生成报告
验证：echo done

## 规则：添加测试结果分析
匹配：添加.*测试.*结果.*分析|analyze.*test|结果.*分析|分析.*结果
工具链：
1. run_shell(python -X utf8 -m pytest --tb=long tests/) — 运行测试
验证：echo done

## 规则：添加测试失败调试
匹配：添加.*测试.*失败.*调试|debug.*test|失败.*调试|调试.*失败
工具链：
1. run_shell(python -X utf8 -m pytest --pdb tests/) — 调试运行测试
验证：echo done

## 规则：添加测试性能分析
匹配：添加.*测试.*性能.*分析|profile.*test|性能.*分析|分析.*性能
工具链：
1. run_shell(python -X utf8 -m pytest --durations=10 tests/) — 性能分析
验证：echo done

## 规则：添加测试依赖检查
匹配：添加.*测试.*依赖.*检查|check.*deps|依赖.*检查|检查.*依赖
工具链：
1. run_shell(pip check) — 检查依赖
验证：pip check

## 规则：添加测试环境检查
匹配：添加.*测试.*环境.*检查|check.*env|环境.*检查|检查.*环境
工具链：
1. run_shell(python --version) — 检查Python版本
2. run_shell(pip list) — 检查已安装包
验证：echo done

## 规则：添加测试配置检查
匹配：添加.*测试.*配置.*检查|check.*config|配置.*检查|检查.*配置
工具链：
1. run_shell(ruff check .) — 检查代码风格
2. run_shell(mypy .) — 检查类型
验证：ruff check . && mypy .

## 规则：添加测试安全检查
匹配：添加.*测试.*安全.*检查|security.*check|安全.*检查|检查.*安全
工具链：
1. run_shell(pip audit) — 安全审计
验证：pip audit

## 规则：添加测试许可证检查
匹配：添加.*测试.*许可证.*检查|license.*check|许可证.*检查|检查.*许可证
工具链：
1. run_shell(pip-licenses) — 许可证检查
验证：echo done

## 规则：添加测试版本检查
匹配：添加.*测试.*版本.*检查|version.*check|版本.*检查|检查.*版本
工具链：
1. run_shell(python -c "import {module}; print({module}.__version__)") — 版本检查
验证：echo done

## 规则：添加测试更新
匹配：添加.*测试.*更新|update.*test|更新.*测试|测试.*更新
工具链：
1. run_shell(pip install --upgrade {package}) — 更新包
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试回滚
匹配：添加.*测试.*回滚|rollback.*test|回滚.*测试|测试.*回滚
工具链：
1. run_shell(git checkout -- {file}) — 回滚文件
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试快照更新
匹配：添加.*测试.*快照.*更新|update.*snapshot|快照.*更新|更新.*快照
工具链：
1. run_shell(python -X utf8 -m pytest --snapshot-update tests/) — 更新快照
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试覆盖率阈值
匹配：添加.*测试.*覆盖率.*阈值|coverage.*threshold|覆盖率.*阈值|阈值.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-fail-under=80 tests/) — 设置阈值
验证：python -X utf8 -m pytest --cov={module} --cov-fail-under=80 tests/

## 规则：添加测试失败重跑
匹配：添加.*测试.*失败.*重跑|rerun.*fail|失败.*重跑|重跑.*失败
工具链：
1. run_shell(python -X utf8 -m pytest --reruns=3 --reruns-delay=1 tests/) — 失败重跑
验证：python -X utf8 -m pytest --reruns=3 tests/

## 规则：添加测试顺序依赖
匹配：添加.*测试.*顺序.*依赖|order.*test|顺序.*依赖|依赖.*顺序
工具链：
1. run_shell(python -X utf8 -m pytest --count=1 tests/) — 顺序运行
验证：python -X utf8 -m pytest tests/

## 规则：添加测试环境隔离
匹配：添加.*测试.*环境.*隔离|isolate.*env|环境.*隔离|隔离.*环境
工具链：
1. write_file({filename}|{code}) — 创建隔离环境
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试数据清理
匹配：添加.*测试.*数据.*清理|cleanup.*data|数据.*清理|清理.*数据
工具链：
1. run_shell(python -X utf8 -m pytest --setup-show tests/) — 显示清理
验证：python -X utf8 -m pytest tests/ -x -q

## 规则：添加测试性能基准
匹配：添加.*测试.*性能.*基准|benchmark.*test|性能.*基准|基准.*性能
工具链：
1. run_shell(python -X utf8 -m pytest --benchmark-only tests/) — 运行基准
验证：python -X utf8 -m pytest --benchmark-only tests/

## 规则：添加测试内存分析
匹配：添加.*测试.*内存.*分析|memory.*test|内存.*分析|分析.*内存
工具链：
1. run_shell(python -X utf8 -m pytest --memray tests/) — 内存分析
验证：echo done

## 规则：添加测试覆盖率排除
匹配：添加.*测试.*覆盖率.*排除|exclude.*coverage|覆盖率.*排除|排除.*覆盖率
工具链：
1. read_file(.coveragerc) — 读取配置
2. replace_in_file(.coveragerc|{old_config}|{new_config}) — 添加排除
验证：echo done

## 规则：添加测试覆盖率分支
匹配：添加.*测试.*覆盖率.*分支|branch.*coverage|覆盖率.*分支|分支.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-branch tests/) — 分支覆盖率
验证：python -X utf8 -m pytest --cov={module} --cov-branch tests/

## 规则：添加测试覆盖率行
匹配：添加.*测试.*覆盖率.*行|line.*coverage|覆盖率.*行|行.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} tests/) — 行覆盖率
验证：python -X utf8 -m pytest --cov={module} tests/

## 规则：添加测试覆盖率函数
匹配：添加.*测试.*覆盖率.*函数|function.*coverage|覆盖率.*函数|函数.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=term-missing tests/) — 函数覆盖率
验证：echo done

## 规则：添加测试覆盖率类
匹配：添加.*测试.*覆盖率.*类|class.*coverage|覆盖率.*类|类.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=term-missing tests/) — 类覆盖率
验证：echo done

## 规则：添加测试覆盖率模块
匹配：添加.*测试.*覆盖率.*模块|module.*coverage|覆盖率.*模块|模块.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=term-missing tests/) — 模块覆盖率
验证：echo done

## 规则：添加测试覆盖率包
匹配：添加.*测试.*覆盖率.*包|package.*coverage|覆盖率.*包|包.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={package} --cov-report=term-missing tests/) — 包覆盖率
验证：echo done

## 规则：添加测试覆盖率项目
匹配：添加.*测试.*覆盖率.*项目|project.*coverage|覆盖率.*项目|项目.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov=. --cov-report=term-missing tests/) — 项目覆盖率
验证：echo done

## 规则：添加测试覆盖率趋势
匹配：添加.*测试.*覆盖率.*趋势|trend.*coverage|覆盖率.*趋势|趋势.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=html tests/) — 生成趋势报告
验证：echo done

## 规则：添加测试覆盖率比较
匹配：添加.*测试.*覆盖率.*比较|compare.*coverage|覆盖率.*比较|比较.*覆盖率
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=term-missing tests/) — 比较覆盖率
验证：echo done

## 规则：添加测试覆盖率阈值检查
匹配：添加.*测试.*覆盖率.*阈值.*检查|check.*threshold|阈值.*检查|检查.*阈值
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-fail-under=80 tests/) — 阈值检查
验证：python -X utf8 -m pytest --cov={module} --cov-fail-under=80 tests/

## 规则：添加测试覆盖率报告生成
匹配：添加.*测试.*覆盖率.*报告.*生成|generate.*report|报告.*生成|生成.*报告
工具链：
1. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=html tests/) — 生成HTML报告
2. run_shell(python -X utf8 -m pytest --cov={module} --cov-report=xml tests/) — 生成XML报告
验证：echo done

## 规则：添加测试覆盖率报告查看
匹配：添加.*测试.*覆盖率.*报告.*查看|view.*report|报告.*查看|查看.*报告
工具链：
1. run_shell(open htmlcov/index.html) — 查看HTML报告
验证：echo done

## 规则：添加测试覆盖率报告上传
匹配：添加.*测试.*覆盖率.*报告.*上传|upload.*report|报告.*上传|上传.*报告
工具链：
1. run_shell(python -m pytest --cov={module} --cov-report=xml tests/) — 生成XML
2. run_shell(bash <(curl -s https://codecov.io/bash)) — 上传报告
验证：echo done

## 规则：添加测试覆盖率报告集成
匹配：添加.*测试.*覆盖率.*报告.*集成|integrate.*report|报告.*集成|集成.*报告
工具链：
1. write_file({filename}|{code}) — 创建集成配置
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告自动化
匹配：添加.*测试.*覆盖率.*报告.*自动化|automate.*report|报告.*自动化|自动化.*报告
工具链：
1. write_file({filename}|{code}) — 创建自动化脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告监控
匹配：添加.*测试.*覆盖率.*报告.*监控|monitor.*report|报告.*监控|监控.*报告
工具链：
1. write_file({filename}|{code}) — 创建监控脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告告警
匹配：添加.*测试.*覆盖率.*报告.*告警|alert.*report|报告.*告警|告警.*报告
工具链：
1. write_file({filename}|{code}) — 创建告警脚本
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告仪表盘
匹配：添加.*测试.*覆盖率.*报告.*仪表盘|dashboard.*report|报告.*仪表盘|仪表盘.*报告
工具链：
1. write_file({filename}|{code}) — 创建仪表盘
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告API
匹配：添加.*测试.*覆盖率.*报告.*API|api.*report|报告.*API|API.*报告
工具链：
1. write_file({filename}|{code}) — 创建API
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告Web界面
匹配：添加.*测试.*覆盖率.*报告.*Web.*界面|web.*report|报告.*Web.*界面|Web.*界面.*报告
工具链：
1. write_file({filename}|{code}) — 创建Web界面
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告CLI
匹配：添加.*测试.*覆盖率.*报告.*CLI|cli.*report|报告.*CLI|CLI.*报告
工具链：
1. write_file({filename}|{code}) — 创建CLI
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done

## 规则：添加测试覆盖率报告插件
匹配：添加.*测试.*覆盖率.*报告.*插件|plugin.*report|报告.*插件|插件.*报告
工具链：
1. write_file({filename}|{code}) — 创建插件
2. run_shell(python -X utf8 -m pytest tests/ -x -q) — 运行测试
验证：echo done
