from __future__ import annotations
import sys
import traceback

from lsp.protocol import _send, _read, _CAPABILITIES
from lsp.analysis import (
    _do_diagnostics,
    _do_completion,
    _do_hover,
    _do_definition,
    _do_signature_help,
    _do_formatting,
    _extract_symbols_for_document,
    _do_folding_ranges,
    _do_references,
    _do_rename,
    _do_prepare_rename,
)

_open_docs: dict[str, str] = {}


def _handle_message(msg: dict) -> None:
    method = msg.get('method', '')
    msg_id = msg.get('id')
    params = msg.get('params', {})

    if method == 'initialize':
        _send(
            {
                'id': msg_id,
                'result': {
                    'capabilities': _CAPABILITIES,
                    'serverInfo': {'name': 'sanyan-lsp', 'version': '0.1.0'},
                },
            }
        )
        _send({'method': 'initialized', 'params': {}})
        return

    if method == 'shutdown':
        _send({'id': msg_id, 'result': None})
        return

    if method == 'exit':
        sys.exit(0)

    if method == 'textDocument/didOpen' or method == 'textDocument/didChange':
        uri = params.get('textDocument', {}).get('uri', '')
        text = ''
        if method == 'textDocument/didOpen':
            text = params.get('textDocument', {}).get('text', '')
        else:
            for change in params.get('contentChanges', []):
                text = change.get('text', '')
        if text:
            diagnostics = _do_diagnostics(uri, text)
            _send(
                {
                    'method': 'textDocument/publishDiagnostics',
                    'params': {'uri': uri, 'diagnostics': diagnostics},
                }
            )
        return

    if method == 'textDocument/completion':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_completion(text, pos)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/hover':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_hover(text, pos)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/definition':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_definition(text, pos, uri)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/signatureHelp':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_signature_help(text, pos)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/formatting':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        result = _do_formatting(text)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/documentSymbol':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        symbols = _extract_symbols_for_document(text)
        _send({'id': msg_id, 'result': symbols})
        return

    if method == 'textDocument/foldingRange':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        ranges = _do_folding_ranges(text)
        _send({'id': msg_id, 'result': ranges})
        return

    if method == 'textDocument/references':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_references(text, pos, uri)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/rename':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        new_name = params.get('newName', '')
        result = _do_rename(text, pos, new_name, uri)
        _send({'id': msg_id, 'result': result})
        return

    if method == 'textDocument/prepareRename':
        uri = params.get('textDocument', {}).get('uri', '')
        text = _open_docs.get(uri, '')
        pos = params.get('position', {})
        result = _do_prepare_rename(text, pos, uri)
        _send({'id': msg_id, 'result': result})
        return

    if msg_id is not None:
        _send({'id': msg_id, 'result': None})


def main() -> None:
    global _open_doc_uri
    while True:
        msg = _read()
        if msg is None:
            break
        params = msg.get('params', {})
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        if uri:
            _open_doc_uri = uri
        if msg.get('method') == 'textDocument/didOpen':
            _open_docs[uri] = td.get('text', '')
        elif msg.get('method') == 'textDocument/didChange':
            for change in params.get('contentChanges', []):
                _open_docs[uri] = change.get('text', '')
        elif msg.get('method') == 'textDocument/didClose':
            _open_docs.pop(uri, None)

        try:
            _handle_message(msg)
        except Exception:
            traceback.print_exc()


if __name__ == '__main__':
    main()
