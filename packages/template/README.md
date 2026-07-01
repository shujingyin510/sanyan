# 三言包模板

快速创建三言包的模板。

## 使用方法

1. 复制 `template` 目录并重命名为你的包名
2. 修改 `package.json` 中的元信息
3. 编写你的代码到 `package.san`
4. 使用 `发布准备("包名")` 打包

## 目录结构

```
my_package/
├── package.json    # 包元信息
├── package.san     # 主入口文件
└── README.md       # 包文档
```

## 导出函数

在 `package.san` 中使用 `导出` 命令导出你的函数：

```san
定义 我的函数(x) {
    返回(加(x, 1))
}

导出 我的函数
```

## 测试

```san
导入("packages/my_package")
输出(我的函数(5))  // => 6
```
