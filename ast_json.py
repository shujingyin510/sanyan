"""AST 序列化：将三言 AST 转换为 JSON 安全的结构。"""
import json
import sys


def ast_to_json(node):
    """递归将 AST 节点转换为 JSON 安全的值。"""
    if isinstance(node, (str, int, float, bool, type(None))):
        return node
    if isinstance(node, list):
        return [ast_to_json(item) for item in node]
    if isinstance(node, dict):
        return {str(k): ast_to_json(v) for k, v in node.items()}
    if hasattr(node, 'to_int'):
        return node.to_int()
    if hasattr(node, 'to_float'):
        return node.to_float()
    return str(node)


def ast_from_file(filepath: str):
    """读取 .san 文件，尝试糖语法解析，失败回退原生解析。"""
    from skin import SkinManager
    from sugar import SugarConverter
    from lexer import tokenize
    from parser import parse
    from preprocess import preprocess_includes

    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    code = preprocess_includes(code)

    skin_mgr = SkinManager('chinese')
    try:
        return SugarConverter.convert(code, skin_mgr)
    except SyntaxError:
        pass

    tokens = tokenize(code)
    if tokens:
        return parse(tokens)
    return None


def main():
    if len(sys.argv) < 2:
        print("用法: python ast_json.py <文件.san>")
        sys.exit(1)
    ast = ast_from_file(sys.argv[1])
    if ast is None:
        print("解析失败")
        sys.exit(1)
    print(json.dumps(ast_to_json(ast), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
