const vscode = require('vscode');
const path = require('path');

function activate(context) {
    const serverModule = context.asAbsolutePath(path.join('..', 'lsp_server.py'));
    const serverOptions = {
        run: { command: 'python', args: [serverModule] },
        debug: { command: 'python', args: [serverModule] },
    };
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'sanyan' }],
        synchronize: { fileEvents: vscode.workspace.createFileSystemWatcher('**/*.san') },
    };
    const client = new vscode.LanguageClient('sanyan-lsp', '三言 Language Server', serverOptions, clientOptions);
    context.subscriptions.push(client.start());
}

function deactivate() {}

module.exports = { activate, deactivate };
