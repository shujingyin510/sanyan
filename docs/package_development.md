# 三言包开发指南

## 概述

三言包是可复用的代码模块，可以通过包管理器安装和分享。本文档介绍如何开发、发布和使用三言包。

## 包结构

```
packages/
  my_package/
    package.san      # 包入口文件（必需）
    package.json     # 包元信息（可选）
    README.md        # 包文档（可选）
    lib/
      helper.san     # 辅助模块（可选）
```

### 入口文件

`package.san` 是包的入口文件，当用户执行 `安装("my_package")` 或 `加载包("my_package")` 时会被加载。

```sanyan
// packages/my_package/package.san

定义 问候(名称) {
    返回(连接("你好，", 名称, "！"))
}

导出 问候
```

### 元信息文件

`package.json` 包含包的元信息：

```json
{
  "name": "my_package",
  "version": "1.0.0",
  "description": "我的三言包",
  "author": "开发者名称",
  "license": "MIT",
  "dependencies": {}
}
```

## 开发流程

### 1. 创建包目录

```bash
mkdir -p packages/my_package
```

### 2. 编写入口文件

创建 `packages/my_package/package.san`：

```sanyan
// 示例：数学工具包

// 计算两点距离
定义 两点距离(x1, y1, x2, y2) {
    设 dx = 减(x2, x1)
    设 dy = 减(y2, y1)
    返回(平方根(加(乘(dx, dx), 乘(dy, dy))))
}

// 计算中点
定义 中点(x1, y1, x2, y2) {
    返回(列表(除(加(x1, x2), 2), 除(加(y1, y2), 2)))
}

导出 两点距离 中点
```

### 3. 测试包

```sanyan
// 测试脚本
设 my = 加载包("my_package")
输出(调用(my, "两点距离", 0, 0, 3, 4))  // 输出: 5
```

### 4. 发布包

将包目录打包为 zip 文件：

```bash
cd packages
zip -r my_package.zip my_package/
```

上传到 GitHub Releases 或其他可访问的 HTTPS 地址。

### 5. 注册到包索引

在 `packages/index.json` 中添加条目：

```json
{
  "my_package": {
    "description": "我的三言包",
    "version": "1.0.0",
    "author": "开发者名称",
    "url": "https://github.com/user/sanyan-packages/releases/download/v1.0.0/my_package.zip"
  }
}
```

## 包管理命令

### 安装包

```sanyan
// 从索引安装
安装("my_package")

// 从 URL 安装
安装("my_package", "https://github.com/user/packages/releases/download/v1.0.0/my_package.zip")
```

### 加载包

```sanyan
设 my = 加载包("my_package")
输出(调用(my, "两点距离", 0, 0, 3, 4))
```

### 列出已安装包

```sanyan
包列表()
```

### 搜索包

```sanyan
搜索("数学")
```

### 查看包信息

```sanyan
包信息("my_package")
```

### 卸载包

```sanyan
卸载("my_package")
```

## 最佳实践

### 1. 命名规范

- 包名使用小写字母和下划线
- 函数名使用中文或英文，保持一致性
- 导出所有公共函数

### 2. 错误处理

```sanyan
定义 安全除法(a, b) {
    若 (等于(b, 0)) {
        返回(列表(假, "除数不能为零"))
    }
    返回(列表(真, 除(a, b)))
}
```

### 3. 文档注释

```sanyan
// 计算阶乘
// 参数：n - 非负整数
// 返回：n 的阶乘值
定义 阶乘(n) {
    若 (小于等于(n, 1)) { 返回(1) }
    返回(乘(n, 阶乘(减(n, 1))))
}
```

### 4. 依赖管理

如果包依赖其他包，在 `package.json` 中声明：

```json
{
  "dependencies": {
    "math_extended": ">=0.1.0"
  }
}
```

### 5. 版本号

使用语义化版本号：`主版本.次版本.修订版本`

- 主版本：不兼容的 API 变更
- 次版本：向下兼容的功能新增
- 修订版本：向下兼容的问题修正

## 示例包

参考 `packages/` 目录下的示例包：

| 包名 | 描述 |
|------|------|
| `sample` | 问候工具示例 |
| `math_extended` | 扩展数学库（复数、向量、统计） |
| `logging` | 结构化日志库 |
| `web_utils` | Web 工具库 |
| `data_pipeline` | 数据处理管道 |
| `config` | 配置管理库 |

## 安全注意事项

- 包下载仅支持 HTTPS 地址
- 域名白名单限制（github.com, gitlab.com, gitee.com）
- zip-slip 防护（防止路径穿越攻击）
- 包代码在隔离环境中执行

## 常见问题

### Q: 包安装失败怎么办？

A: 检查网络连接，确认 URL 可访问，查看错误信息。

### Q: 如何更新包？

A: 卸载后重新安装：`卸载("my_package")` 然后 `安装("my_package")`

### Q: 包之间如何共享数据？

A: 通过函数参数和返回值传递，避免全局状态。

### Q: 如何调试包？

A: 使用 `输出()` 打印调试信息，或使用 `logging` 包的日志功能。
