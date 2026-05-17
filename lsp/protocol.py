from __future__ import annotations
import json
import sys
from typing import Optional

_CONTENT_LENGTH_HEADER = 'Content-Length: '


def _send(msg: dict) -> None:
    body = json.dumps(msg, ensure_ascii=False)
    data = body.encode('utf-8')
    header = f'{_CONTENT_LENGTH_HEADER}{len(data)}\r\n\r\n'
    sys.stdout.buffer.write(header.encode() + data)
    sys.stdout.buffer.flush()


def _read() -> Optional[dict]:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode('utf-8', errors='replace').strip()
        if not line:
            break
        if line.startswith(_CONTENT_LENGTH_HEADER):
            headers['content-length'] = int(line[len(_CONTENT_LENGTH_HEADER) :])
    length = headers.get('content-length', 0)
    if length == 0:
        return None
    body = sys.stdin.buffer.read(length).decode('utf-8', errors='replace')
    return json.loads(body)


_CAPABILITIES = {
    'textDocumentSync': {
        'openClose': True,
        'change': {'syncKind': 1},
    },
    'completionProvider': {
        'triggerCharacters': ['.', '（', '(', '：'],
        'resolveProvider': False,
    },
    'hoverProvider': True,
    'definitionProvider': True,
    'signatureHelpProvider': {
        'triggerCharacters': ['(', '（'],
    },
    'documentFormattingProvider': True,
    'documentSymbolProvider': True,
    'foldingRangeProvider': True,
    'referencesProvider': True,
    'renameProvider': {'prepareProvider': True},
}
