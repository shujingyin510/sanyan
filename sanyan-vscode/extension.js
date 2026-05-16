const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');

let serverProcess = null;

function findServerPath() {
    const extDir = path.dirname(__dirname);
    const candidates = [
        path.join(extDir, 'lsp_server.py'),
        path.join(__dirname, '..', 'lsp_server.py'),
        path.join(__dirname, '..', '..', 'lsp_server.py'),
    ];
    for (const p of candidates) {
        try { require('fs').accessSync(p); return p; } catch (_) {}
    }
    return null;
}

function startServer() {
    const serverPath = findServerPath();
    if (!serverPath) {
        vscode.window.showWarningMessage('三言 LSP 服务器 (lsp_server.py) 未找到');
        return null;
    }
    try {
        const proc = spawn('python', [serverPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: path.dirname(serverPath),
        });
        proc.on('error', () => vscode.window.showWarningMessage('无法启动三言 LSP 服务器。确保 Python 已安装。'));
        proc.on('exit', (code) => {
            if (code !== 0) console.error('LSP server exited with code', code);
            serverProcess = null;
        });
        return proc;
    } catch (e) {
        vscode.window.showWarningMessage(`启动 LSP 服务器失败: ${e.message}`);
        return null;
    }
}

class LspClient {
    constructor(proc, onNotification) {
        this.proc = proc;
        this.reqId = 1;
        this.pending = new Map();
        this.buffer = '';
        this.onNotification = onNotification || (() => {});
        proc.stdout.on('data', (chunk) => this._onData(chunk));
    }

    _onData(chunk) {
        this.buffer += chunk.toString();
        while (true) {
            const headerEnd = this.buffer.indexOf('\r\n\r\n');
            if (headerEnd === -1) break;
            const header = this.buffer.slice(0, headerEnd);
            const m = header.match(/Content-Length: (\d+)/i);
            if (!m) { this.buffer = this.buffer.slice(headerEnd + 4); continue; }
            const len = parseInt(m[1], 10);
            const bodyStart = headerEnd + 4;
            if (this.buffer.length < bodyStart + len) break;
            const body = this.buffer.slice(bodyStart, bodyStart + len);
            this.buffer = this.buffer.slice(bodyStart + len);
            try {
                const msg = JSON.parse(body);
                this._handle(msg);
            } catch (_) {}
        }
    }

    _handle(msg) {
        if (msg.id != null && this.pending.has(msg.id)) {
            const { resolve } = this.pending.get(msg.id);
            this.pending.delete(msg.id);
            resolve(msg);
        } else if (msg.method) {
            this.onNotification(msg);
        }
    }

    send(method, params) {
        const id = this.reqId++;
        const msg = { jsonrpc: '2.0', id, method, params };
        const body = JSON.stringify(msg);
        this.proc.stdin.write(`Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`);
        return new Promise((resolve) => this.pending.set(id, { resolve }));
    }

    notify(method, params) {
        const msg = { jsonrpc: '2.0', method, params };
        const body = JSON.stringify(msg);
        this.proc.stdin.write(`Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`);
    }

    close() {
        this.proc.stdin.end();
        this.proc.kill();
    }
}

function activate(context) {
    const proc = startServer();
    const diag = vscode.languages.createDiagnosticCollection('sanyan');
    let client = null;

    if (proc) {
        client = new LspClient(proc, (msg) => {
            if (msg.method === 'textDocument/publishDiagnostics') {
                const uri = vscode.Uri.parse(msg.params.uri);
                diag.set(uri, (msg.params.diagnostics || []).map((d) => {
                    const r = d.range;
                    return new vscode.Diagnostic(
                        new vscode.Range(r.start.line, r.start.character, r.end.line, r.end.character),
                        d.message,
                        d.severity === 1 ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning
                    );
                }));
            }
        });
        client.send('initialize', {
            processId: process.pid,
            capabilities: {
                textDocument: {
                    completion: { completionItem: { snippetSupport: false } },
                    hover: true, definition: true, signatureHelp: true,
                    synchronization: { didOpen: true, didChange: true, didClose: true },
                },
            },
        }).then(() => client.notify('initialized', {}));
    }

    const triggerChars = '设若循遍定返跳继续尝试捕判函λ在导入输出加载出注册备对置读查加减乘除余幂大小等于且或非真假可能开关守'.split('');

    const completionProvider = vscode.languages.registerCompletionItemProvider(
        { scheme: 'file', language: 'sanyan' },
        {
            async provideCompletionItems(document, position) {
                if (!client) {
                    return '设,若,再若,否则,循环,遍历,定义,返回,跳出,继续,尝试,捕获,判,函数,λ,在,导入,输出,加载,导出,注册设备,对,置,读,查,加,减,乘,除,余,幂,大于,小于,等于,不等于,且,或,非,真,假,可能,开,关,守'.split(',').map(k => {
                        const item = new vscode.CompletionItem(k, vscode.CompletionItemKind.Keyword);
                        item.range = document.getWordRangeAtPosition(position);
                        return item;
                    });
                }
                try {
                    const result = await client.send('textDocument/completion', {
                        textDocument: { uri: document.uri.toString() },
                        position: { line: position.line, character: position.character },
                    });
                    return (result.result || []).map((i) => {
                        const item = new vscode.CompletionItem(i.label, vscode.CompletionItemKind[i.kind] || vscode.CompletionItemKind.Text);
                        if (i.detail) item.detail = i.detail;
                        if (i.documentation) item.documentation = i.documentation;
                        return item;
                    });
                } catch (_) { return []; }
            },
        },
        ...triggerChars
    );

    const hoverProvider = vscode.languages.registerHoverProvider(
        { scheme: 'file', language: 'sanyan' },
        {
            async provideHover(document, position) {
                if (!client) return null;
                try {
                    const result = await client.send('textDocument/hover', {
                        textDocument: { uri: document.uri.toString() },
                        position: { line: position.line, character: position.character },
                    });
                    const h = result.result;
                    return h ? new vscode.Hover(h.contents) : null;
                } catch (_) { return null; }
            },
        }
    );

    const defProvider = vscode.languages.registerDefinitionProvider(
        { scheme: 'file', language: 'sanyan' },
        {
            async provideDefinition(document, position) {
                if (!client) return null;
                try {
                    const result = await client.send('textDocument/definition', {
                        textDocument: { uri: document.uri.toString() },
                        position: { line: position.line, character: position.character },
                    });
                    const loc = result.result;
                    return loc ? new vscode.Location(vscode.Uri.parse(loc.uri), new vscode.Position(loc.range.start.line, loc.range.start.character)) : null;
                } catch (_) { return null; }
            },
        }
    );

    const openSub = vscode.workspace.onDidOpenTextDocument((doc) => {
        if (doc.languageId !== 'sanyan' || !client) return;
        client.notify('textDocument/didOpen', {
            textDocument: { uri: doc.uri.toString(), languageId: 'sanyan', version: 1, text: doc.getText() },
        });
    });

    const changeSub = vscode.workspace.onDidChangeTextDocument((e) => {
        if (e.document.languageId !== 'sanyan' || !client) return;
        client.notify('textDocument/didChange', {
            textDocument: { uri: e.document.uri.toString(), version: e.document.version + 1 },
            contentChanges: [{ text: e.document.getText() }],
        });
    });

    context.subscriptions.push(
        completionProvider, hoverProvider, defProvider,
        openSub, changeSub, diag,
        { dispose: () => { if (client) client.close(); if (proc) proc.kill(); } }
    );
}

function deactivate() {
    if (serverProcess) serverProcess.kill();
}

module.exports = { activate, deactivate };
