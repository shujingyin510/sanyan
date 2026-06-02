# 三言 VS Code Extension

> **注意**：因 VS Code Marketplace 上架需银行卡验证，当前仅支持本地安装。

## 安装方法

### 方法一：命令行安装（推荐）

```bash
cd sanyan-vscode
npm install -g @vscode/vsce
vsce package
code --install-extension sanyan-0.2.0.vsix
```

### 方法二：图形界面安装

1. 在 VS Code 中按 `Ctrl+Shift+P` (或 `Cmd+Shift+P`)
2. 输入并选择 **Extensions: Install from VSIX...**
3. 选择 `sanyan-0.2.0.vsix` 文件

### 方法三：开发调试

1. 用 VS Code 打开 `sanyan-vscode/` 文件夹
2. 按 `F5` 启动 Extension Development Host

## 功能
- 语法高亮（关键字、字符串、数字、注释）
- 关键字补全（含用户定义的变量和函数）
- 悬停提示（内置函数文档 + 用户自定义文档注释）
- 跳转到定义（函数 + 变量）
- 签名帮助（函数参数提示）
- 格式化（sanfmt 格式化器）
- 文档符号（大纲视图）
- 折叠范围（{} 块折叠）
- 引用查找（所有使用处高亮）
- 批量重命名
- 诊断（括号匹配 + 重复参数检测）
