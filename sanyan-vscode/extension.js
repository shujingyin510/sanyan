const vscode = require('vscode');

function activate(context) {
    console.log('三言 extension activated');

    // 注册简单的补全提供者（不依赖 LSP 客户端）
    const keywords = [
        '设', '若', '再若', '否则', '循环', '遍历', '定义', '返回',
        '跳出', '继续', '尝试', '捕获', '判', '函数', 'λ', '在',
        '导入', '输出', '加载', '导出', '注册设备', '对', '置', '读', '查',
        '加', '减', '乘', '除', '余', '幂',
        '大于', '小于', '等于', '不等于', '且', '或', '非',
        '真', '假', '可能', '开', '关', '守',
    ];

    const provider = vscode.languages.registerCompletionItemProvider(
        { scheme: 'file', language: 'sanyan' },
        {
            provideCompletionItems(document, position) {
                const items = keywords.map(k => {
                    const item = new vscode.CompletionItem(k, vscode.CompletionItemKind.Keyword);
                    item.range = document.getWordRangeAtPosition(position);
                    return item;
                });
                return items;
            }
        },
        ...keywords.map(k => k[0])
    );

    context.subscriptions.push(provider);
}

function deactivate() {}

module.exports = { activate, deactivate };
