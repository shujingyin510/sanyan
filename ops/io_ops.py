"""输入/输出、调试、值格式化、等待"""

import time
from ternary_core import TritValue
from values import FunctionValue, ModuleValue, SanyanValueError, SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class IOOps:
    """I/O 操作：输出、格式化、打印、用户输入"""

    @staticmethod
    def format_value(val):
        """将三言值格式化为美观字符串，容器附三进制注释"""
        from ternary_core import TritValue, ArrayValue

        if isinstance(val, list):
            items_int = []
            items_trit = []
            for v in val:
                if isinstance(v, TritValue):
                    if v.is_float():
                        items_int.append(str(v.to_float()))
                    else:
                        items_int.append(str(v.to_int()))
                    items_trit.append(str(v.symbol))
                else:
                    items_int.append(str(v))
                    items_trit.append('?')
            base = '[' + ', '.join(items_int) + ']'
            if items_trit and not all(t == '?' for t in items_trit):
                base += '（三进制: ' + ', '.join(items_trit) + '）'
            return base
        elif isinstance(val, ArrayValue):
            return IOOps.format_value(val.data)  # 重用列表格式化
        elif isinstance(val, dict):
            return str(val)
        elif isinstance(val, TritValue):
            if val.is_float():
                return f'{val.to_float()}（三进制: {val.symbol}）'
            return f'{val.to_int()}（三进制: {val.symbol}）'
        else:
            return str(val)

    @staticmethod
    def output(evaluator, args):
        if len(args) == 0:
            return TritValue(0)
        val = evaluator.eval(args[0])
        formatted = IOOps.format_value(val)
        print(f'  => {formatted}')
        return val

    @staticmethod
    def input_op(evaluator, args):
        prompt = '请输入一个值: '
        if args:
            prompt = str(args[0])
        user_input = input(prompt).strip()
        try:
            return TritValue(float(user_input))
        except ValueError:
            pass
        if user_input in TritValue.STATE_MAP:
            return TritValue.from_string(user_input)
        return user_input  # 纯文本直接返回

    @staticmethod
    def debug_op(evaluator, args):
        # 检查是否是断点模式
        if args:
            mode = evaluator.eval(args[0])
            if isinstance(mode, str) and mode == '断点':
                return IOOps._breakpoint(evaluator)

        # 普通调试信息
        print('=== 调试信息 ===')
        print(f'调用栈深度: {evaluator.call_depth}')
        if evaluator.call_stack:
            last_op, last_args = evaluator.call_stack[-1]
            print(f'最近调用: {last_op}')
        print('变量:')
        for name, val in evaluator.all_scoped_vars().items():
            type_name = type(val).__name__
            if isinstance(val, TritValue):
                type_name = '三值整数'
                print(f'  {name}: {val} (类型: {type_name}, 三进制: {val.symbol})')
            elif isinstance(val, str):
                type_name = '字符串'
                print(f'  {name}: "{val}" (类型: {type_name}, 长度: {len(val)})')
            elif isinstance(val, list):
                type_name = '列表'
                print(f'  {name}: {val} (类型: {type_name}, 长度: {len(val)})')
            elif isinstance(val, dict):
                type_name = '字典'
                print(f'  {name}: {val} (类型: {type_name}, 键数: {len(val)})')
            elif isinstance(val, FunctionValue):
                type_name = '函数'
                print(f'  {name}: {val} (类型: {type_name})')
            elif isinstance(val, ModuleValue):
                type_name = '模块'
                print(f'  {name}: {val} (类型: {type_name})')
            else:
                print(f'  {name}: {val} (类型: {type_name})')
        print('传感器:')
        for name, val in evaluator.sensors.items():
            print(f'  {name}: {val.symbol} (int: {val.to_int()})')
        print('执行器:')
        for name, val in evaluator.actuators.items():
            print(f'  {name}: {val.symbol} (int: {val.to_int()})')
        print('================')
        return TritValue(0)

    @staticmethod
    def _breakpoint(evaluator):
        """断点调试：暂停执行，进入交互式调试模式"""
        print('\n=== 断点 ===')
        print('命令: (继续) 继续执行, (变量) 查看变量, (传感器) 查看传感器, (执行器) 查看执行器')
        print('输入表达式可求值，输入 (继续) 恢复执行')

        while True:
            try:
                cmd = input('调试> ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\n继续执行...')
                break

            if not cmd:
                continue

            if cmd in ('（继续）', '继续', '(继续)', 'continue', 'c'):
                print('继续执行...')
                break
            elif cmd in ('（变量）', '变量', '(变量)', 'vars', 'v'):
                print('变量:')
                for name, val in evaluator.all_scoped_vars().items():
                    print(f'  {name}: {val}')
            elif cmd in ('（传感器）', '传感器', '(传感器)', 'sensors', 's'):
                print('传感器:')
                for name, val in evaluator.sensors.items():
                    print(f'  {name}: {val.symbol} (int: {val.to_int()})')
            elif cmd in ('（执行器）', '执行器', '(执行器)', 'actuators', 'a'):
                print('执行器:')
                for name, val in evaluator.actuators.items():
                    print(f'  {name}: {val.symbol} (int: {val.to_int()})')
            elif cmd in ('（帮助）', '帮助', '(帮助)', 'help', 'h', '?'):
                print('命令:')
                print('  (继续) / c - 继续执行')
                print('  (变量) / v - 查看所有变量')
                print('  (传感器) / s - 查看传感器状态')
                print('  (执行器) / a - 查看执行器状态')
                print('  (帮助) / h - 显示此帮助')
                print('  其他输入将作为三言表达式求值')
            else:
                # 尝试作为表达式求值
                try:
                    from sugar import SugarConverter

                    ast = SugarConverter.convert(cmd, evaluator.skin_manager)
                    result = evaluator.eval(ast)
                    if result is not None:
                        formatted = IOOps.format_value(result)
                        print(f'  => {formatted}')
                except (SyntaxError, SanyanValueError, SanyanSyntaxError) as e:
                    print(f'  错误: {e}')

        return TritValue(0)

    @staticmethod
    def wait_op(evaluator, args):
        """等待指定毫秒数：等待 1000"""
        if len(args) == 0:
            raise SanyanSyntaxError('等待 需要一个参数（毫秒数）')
        ms = evaluator.eval(args[0])
        if isinstance(ms, TritValue):
            ms = ms.to_int()
        elif isinstance(ms, (int, float)):
            ms = int(ms)
        else:
            raise SanyanTypeError(f'等待 参数必须是数字，但得到: {type(ms).__name__}')
        if ms < 0:
            raise SanyanValueError(f'等待 参数不能为负数: {ms}')
        time.sleep(ms / 1000.0)
        return TritValue(0)


# 注册 IO 操作
register('print', IOOps.output)
register('input', IOOps.input_op)
register('debug', IOOps.debug_op)
register('wait', IOOps.wait_op)
