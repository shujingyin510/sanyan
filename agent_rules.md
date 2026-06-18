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
匹配：新增.*模块.*\.py|创建.*\.py|写.*函数.*到|实现.*模块
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
