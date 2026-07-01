# 三言包开发指南

## 快速开始

### 1. 创建包目录

```bash
mkdir packages/my_package
cd packages/my_package
```

### 2. 创建 package.json

```json
{
  "name": "my_package",
  "version": "1.0.0",
  "description": "我的包描述",
  "author": "你的名字",
  "license": "GPL-3.0",
  "keywords": ["keyword1", "keyword2"],
  "main": "package.san"
}
```

### 3. 编写 package.san

```san
// 我的包主入口

定义 我的函数(x) {
    返回(加(x, 1))
}

定义 另一个函数(x, y) {
    返回(加(x, y))
}

导出 我的函数 另一个函数
```

### 4. 测试包

```san
// test_my_package.san
导入("packages/my_package")

输出(我的函数(5))  // => 6
输出(另一个函数(3, 4))  // => 7
```

## 包结构

```
my_package/
├── package.json    # 包元信息（必需）
├── package.san     # 主入口文件（必需）
├── README.md       # 包文档（推荐）
├── test.san        # 测试文件（推荐）
└── lib/            # 辅助模块（可选）
    ├── utils.san
    └── helpers.san
```

## package.json 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| name | string | ✓ | 包名（小写，可用连字符） |
| version | string | ✓ | 语义化版本号 |
| description | string | ✓ | 包描述 |
| author | string | ✓ | 作者 |
| license | string | | 许可证（默认 GPL-3.0） |
| keywords | string[] | | 关键词标签 |
| main | string | | 入口文件（默认 package.san） |
| dependencies | object | | 依赖包列表 |

## 导出函数

使用 `导出` 命令导出包的公共 API：

```san
定义 公共函数() { ... }
定义 内部函数() { ... }  // 不导出

导出 公共函数
```

## 依赖管理

在 package.json 中声明依赖：

```json
{
  "dependencies": {
    "math_utils": ">=1.0.0",
    "string_utils": "^2.0.0"
  }
}
```

版本约束格式：
- `>=1.0.0` — 大于等于
- `<2.0.0` — 小于
- `^1.0.0` — 兼容版本（>=1.0.0, <2.0.0）
- `~1.0.0` — 补丁版本（>=1.0.0, <1.1.0）

## 测试

创建 `test.san` 文件：

```san
导入("packages/my_package")
导入("stdlib/test")

测试套件("我的包测试")

测试("我的函数测试", 函数() {
    返回(断言相等(我的函数(5), 6))
})

测试("另一个函数测试", 函数() {
    返回(断言相等(另一个函数(3, 4), 7))
})

测试报告()
```

运行测试：

```bash
python -X utf8 main.py test_my_package.san
```

## 发布

### 1. 准备发布

```san
发布准备("my_package")
```

这会创建 `build/my_package.zip` 文件。

### 2. 上传到 GitHub

1. Fork [sanyan-packages](https://github.com/shujingyin510/sanyan-packages) 仓库
2. 将 zip 文件上传到 `packages/` 目录
3. 更新 `index.json` 添加你的包信息
4. 提交 Pull Request

### 3. 本地安装

```san
安装("my_package", "path/to/my_package.zip")
```

## 最佳实践

### 命名规范

- 包名：小写，用连字符分隔（`my-package`）
- 函数名：中文或英文均可，保持一致性
- 常量：大写（`MAX_SIZE`）

### 错误处理

```san
定义 安全除法(a, b) {
    若 (等于(b, 0)) {
        返回(无)  // 或抛出异常
    }
    返回(除(a, b))
}
```

### 文档注释

```san
// 计算两个数的和
// 参数:
//   a - 第一个数
//   b - 第二个数
// 返回: 两数之和
定义 加法(a, b) {
    返回(加(a, b))
}
```

### 性能优化

- 避免不必要的循环
- 使用缓存减少重复计算
- 避免深层递归（使用尾递归优化）

## 示例包

参考现有包：

- `packages/sample` — 简单示例
- `packages/math_extended` — 数学扩展
- `packages/logging` — 日志库
- `packages/json_utils` — JSON 工具
- `packages/string_utils` — 字符串工具

## 常见问题

### Q: 如何导入其他包？

```san
导入("packages/other_package")
```

### Q: 如何使用标准库？

```san
导入("stdlib/math")
导入("stdlib/string")
```

### Q: 如何处理版本冲突？

使用版本约束确保兼容性：

```json
{
  "dependencies": {
    "math_utils": ">=1.0.0,<2.0.0"
  }
}
```

### Q: 如何调试包？

使用 `输出` 命令或调试器：

```san
输出("调试信息: ", 变量)
调试(变量)
```
