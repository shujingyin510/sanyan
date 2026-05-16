# 三言 VS Code Extension

安装方法：
1. 在 VS Code 中按 `Ctrl+Shift+P` (或 `Cmd+Shift+P`)
2. 输入并选择 **Extensions: Install from VSIX...**
3. 或选择 **File → Open Folder...** 打开 `sanyan-vscode/` 文件夹
4. 按 `F5` 启动 Extension Development Host

或者用命令行打包：
```bash
cd sanyan-vscode
npm install -g vsce
vsce package
code --install-extension sanyan-language-0.1.0.vsix
```

功能：
- 语法高亮（关键字、字符串、数字、注释）
- 基础关键字补全
