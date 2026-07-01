"""字节码 VM 单元测试：直接构造字节码验证每条指令"""

import os
import struct
import tempfile


import unittest
from vm import (
    VM,
    VMError,
    NOP,
    PUSH_I,
    ADD,
    SUB,
    MUL,
    DIV,
    MOD,
    LOAD,
    STORE,
    JMP,
    JZ,
    JNZ,
    CALL,
    RET,
    EQ,
    NE,
    GT,
    LT,
    GTE,
    LTE,
    NOT,
    CONCAT,
    STRLEN,
    STRSUB,
    STREQ,
    ORD,
    PUSH_STR,
    DICT,
    DICT_GET,
    DICT_SET,
    DICT_HAS,
    DICT_KEYS,
    IS_NUM,
    IS_STR,
    IS_LIST,
    SAME,
    GET,
    SET_ELEMENT,
    LIST_NEW,
    LIST_CONCAT,
    SLICE,
    LIST_LEN,
    READ_FILE,
    WRITE_FILE,
    HALT,
    PRINT,
    AND,
    IO_READ,
    IO_WRITE,
    STR_TO_LIST,
    DICT_LEN,
    JMP32,
)


def _make_vm(code_bytes, vars_count=256):
    return VM(bytearray(code_bytes), vars_count=vars_count)


def _push_i(val):
    return list(struct.pack('<B', PUSH_I)) + list(struct.pack('<i', val))


def _halt():
    return [HALT]


def _push_str(s):
    """构造 PUSH_STR 字节码：PUSH_STR + 长度 + UTF-16LE 字符"""
    code = [PUSH_STR, len(s)]
    for ch in s:
        code.extend([ord(ch) & 0xFF, (ord(ch) >> 8) & 0xFF])
    return code


class TestStackOps(unittest.TestCase):
    def test_push_i(self):
        vm = _make_vm(_push_i(42) + _halt())
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_push_i_negative(self):
        vm = _make_vm(_push_i(-7) + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-7])

    def test_push_i_zero(self):
        vm = _make_vm(_push_i(0) + _halt())
        vm.run()
        self.assertEqual(vm.stack, [0])

    def test_push_str(self):
        s = 'Hi'
        code = [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, (ord(ch) >> 8) & 0xFF])
        code += _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, ['Hi'])

    def test_push_str_empty(self):
        vm = _make_vm([PUSH_STR, 0] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [''])

    def test_push_str_chinese(self):
        s = '你好'
        code = [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, (ord(ch) >> 8) & 0xFF])
        code += _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, ['你好'])


class TestArithmetic(unittest.TestCase):
    def test_add(self):
        vm = _make_vm(_push_i(3) + _push_i(4) + [ADD] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [7])

    def test_sub(self):
        vm = _make_vm(_push_i(10) + _push_i(3) + [SUB] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [7])

    def test_mul(self):
        vm = _make_vm(_push_i(6) + _push_i(7) + [MUL] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_div(self):
        vm = _make_vm(_push_i(10) + _push_i(3) + [DIV] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [3])

    def test_div_by_zero(self):
        vm = _make_vm(_push_i(10) + _push_i(0) + [DIV] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [0])

    def test_mod(self):
        vm = _make_vm(_push_i(10) + _push_i(3) + [MOD] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_mod_by_zero(self):
        vm = _make_vm(_push_i(10) + _push_i(0) + [MOD] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [0])


class TestComparison(unittest.TestCase):
    def test_eq_true(self):
        vm = _make_vm(_push_i(5) + _push_i(5) + [EQ] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_eq_false(self):
        vm = _make_vm(_push_i(5) + _push_i(3) + [EQ] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_ne(self):
        vm = _make_vm(_push_i(5) + _push_i(3) + [NE] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_gt(self):
        vm = _make_vm(_push_i(5) + _push_i(3) + [GT] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_gt_false(self):
        vm = _make_vm(_push_i(3) + _push_i(5) + [GT] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_lt(self):
        vm = _make_vm(_push_i(3) + _push_i(5) + [LT] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_gte(self):
        vm = _make_vm(_push_i(5) + _push_i(5) + [GTE] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_lte(self):
        vm = _make_vm(_push_i(5) + _push_i(5) + [LTE] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_not_zero(self):
        vm = _make_vm(_push_i(0) + [NOT] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [0])  # 三值逻辑: NOT(0)=可能(0)

    def test_not_nonzero(self):
        vm = _make_vm(_push_i(42) + [NOT] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：NOT >0 = -1


class TestVariableOps(unittest.TestCase):
    def test_store_load(self):
        code = _push_i(99) + [STORE, 0] + [LOAD, 0] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [99])
        self.assertEqual(vm.vars[0], 99)

    def test_load_uninitialized(self):
        code = [LOAD, 0] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [0])

    def test_store_multiple(self):
        code = _push_i(10) + [STORE, 0] + _push_i(20) + [STORE, 1] + [LOAD, 0] + [LOAD, 1] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [10, 20])


class TestControlFlow(unittest.TestCase):
    def test_jmp_forward(self):
        # JMP offset is relative to pc AFTER reading the i16 offset.
        # [0-4] PUSH_I 99 (5B)
        # [5-7] JMP → after reading: pc=8. We want to skip to HALT at byte 13.
        #   offset = 13 - 8 = 5
        # [8-12] PUSH_I 42 (5B, skipped)
        # [13] HALT
        code = _push_i(99) + [JMP, 5, 0] + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [99])

    def test_jz_zero_jumps(self):
        # [0-4] PUSH_I 0 (5B)
        # [5]   JZ (1B) → after reading i16: pc=8
        # [6-7] offset=5 → pc+=5 → pc=13, skip PUSH_I 99 at [8-12]
        # [13-17] PUSH_I 42
        # [18] HALT
        code = _push_i(0) + [JZ, 5, 0] + _push_i(99) + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_jz_nonzero_no_jump(self):
        # [0-4] PUSH_I 1 (5B)
        # [5]   JZ offset=0 → after reading: pc=8, pc+=0 → pc=8
        # [8-12] PUSH_I 42
        code = _push_i(1) + [JZ, 0, 0] + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_jnz_nonzero_jumps(self):
        # [0-4] PUSH_I 1
        # [5]   JNZ → after reading: pc=8, offset=5 → pc=13 (skip PUSH_I 99)
        # [8-12] PUSH_I 99 (skipped)
        # [13-17] PUSH_I 42
        code = _push_i(1) + [JNZ, 5, 0] + _push_i(99) + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_jnz_zero_no_jump(self):
        # [0-4] PUSH_I 0
        # [5]   JNZ offset=0 → no jump → pc=8
        # [8-12] PUSH_I 42
        code = _push_i(0) + [JNZ, 0, 0] + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_jmp32(self):
        # JMP32: 1B opcode + 4B i32. After reading: pc=5. pc+=offset.
        # We want pc=10 (start of PUSH_I 42). offset=5.
        # [0-4]   JMP32
        # [5-9]   PUSH_I 99 (skipped)
        # [10-14] PUSH_I 42
        # [15]    HALT
        code = [JMP32] + list(struct.pack('<i', 5)) + _push_i(99) + _push_i(42) + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_loop_count_down(self):
        # [0-4]   PUSH_I 3
        # [5-6]   STORE 0
        # [7-8]   LOAD 0
        # [9-13]  PUSH_I 1
        # [14]    SUB
        # [15-16] STORE 0
        # [17-18] LOAD 0
        # [19]    JNZ (1B opcode + 2B offset) → after reading: pc=22
        # We want to jump to [7]. offset = 7 - 22 = -15
        code = (
            _push_i(3)
            + [STORE, 0]
            + [LOAD, 0]
            + _push_i(1)
            + [SUB]
            + [STORE, 0]
            + [LOAD, 0]
            + [JZ if False else JNZ, 0xF1, 0xFF]  # -15 as i16 LE
            + _halt()
        )
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.vars[0], 0)


class TestStringOps(unittest.TestCase):
    def test_concat(self):
        s1, s2 = 'AB', 'XY'
        code = [PUSH_STR, len(s1)]
        for ch in s1:
            code.extend([ord(ch) & 0xFF, 0])
        code += [PUSH_STR, len(s2)]
        for ch in s2:
            code.extend([ord(ch) & 0xFF, 0])
        code += [CONCAT] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, ['ABXY'])

    def test_strlen(self):
        s = 'Hello'
        code = [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, (ord(ch) >> 8) & 0xFF])
        code += [STRLEN] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [5])

    def test_strsub(self):
        s = 'Hello'
        code = [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, (ord(ch) >> 8) & 0xFF])
        code += _push_i(1) + _push_i(3) + [STRSUB] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, ['ell'])

    def test_streq_same(self):
        s = 'abc'
        code = [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, 0])
        code += [PUSH_STR, len(s)]
        for ch in s:
            code.extend([ord(ch) & 0xFF, 0])
        code += [STREQ] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_streq_diff(self):
        code = [PUSH_STR, 3, ord('a') & 0xFF, 0, ord('b') & 0xFF, 0, ord('c') & 0xFF, 0]
        code += [PUSH_STR, 1, ord('x') & 0xFF, 0]
        code += [STREQ] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_ord(self):
        code = [PUSH_STR, 1, ord('A') & 0xFF, 0] + [ORD] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [65])


class TestTypeCheck(unittest.TestCase):
    def test_is_num(self):
        vm = _make_vm(_push_i(42) + [IS_NUM] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_is_num_string(self):
        code = [PUSH_STR, 3, ord('a') & 0xFF, 0, ord('b') & 0xFF, 0, ord('c') & 0xFF, 0]
        code += [IS_NUM] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_is_str(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + [IS_STR] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_is_str_number(self):
        vm = _make_vm(_push_i(42) + [IS_STR] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_is_list_on_list(self):
        vm = _make_vm(_push_i(0) + [LIST_NEW] + [IS_LIST] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_is_list_on_int(self):
        vm = _make_vm(_push_i(42) + [IS_LIST] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_same(self):
        vm = _make_vm(_push_i(42) + _push_i(42) + [SAME] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_same_different(self):
        vm = _make_vm(_push_i(42) + _push_i(43) + [SAME] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1


class TestListOps(unittest.TestCase):
    def test_list_new_empty(self):
        vm = _make_vm(_push_i(0) + [LIST_NEW] + _halt())
        vm.run()
        self.assertEqual(vm.stack, [[]])

    def test_list_new_3(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(3) + [LIST_NEW] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [[10, 20, 30]])

    def test_list_len(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(3) + [LIST_NEW] + [LIST_LEN] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [3])

    def test_list_concat(self):
        code = _push_i(1) + _push_i(2) + _push_i(2) + [LIST_NEW]
        code += _push_i(3) + _push_i(4) + _push_i(2) + [LIST_NEW]
        code += [LIST_CONCAT] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [[1, 2, 3, 4]])

    def test_get_by_index(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(3) + [LIST_NEW]
        code += _push_i(1) + [GET] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [20])

    def test_set_element(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(3) + [LIST_NEW]
        code += _push_i(1) + _push_i(99) + [SET_ELEMENT] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [[10, 99, 30]])

    def test_slice_3args(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(40) + _push_i(4) + [LIST_NEW]
        code += _push_i(1) + _push_i(3) + [SLICE] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [[20, 30]])

    def test_slice_2args(self):
        code = _push_i(10) + _push_i(20) + _push_i(30) + _push_i(3) + [LIST_NEW]
        code += _push_i(1) + [SLICE] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [[20, 30]])


class TestDictOps(unittest.TestCase):
    def test_dict_new(self):
        code = [PUSH_STR, 1, ord('a') & 0xFF, 0] + _push_i(42) + _push_i(1) + [DICT] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [{'a': 42}])

    def test_dict_get(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [PUSH_STR, 1, ord('x') & 0xFF, 0] + [DICT_GET] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [99])

    def test_dict_get_missing(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [PUSH_STR, 1, ord('y') & 0xFF, 0] + [DICT_GET] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [''])

    def test_dict_set_and_get(self):
        # Build dict, store in var, set key, get key
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [STORE, 0]  # vars[0] = dict
        # DICT_SET pops val, key, dict (in that order)
        code += [LOAD, 0] + [PUSH_STR, 1, ord('y') & 0xFF, 0] + _push_i(42) + [DICT_SET]
        # DICT_GET pops key, dict
        code += [LOAD, 0] + [PUSH_STR, 1, ord('y') & 0xFF, 0] + [DICT_GET] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_dict_has(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [PUSH_STR, 1, ord('x') & 0xFF, 0] + [DICT_HAS] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [1])

    def test_dict_has_missing(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [PUSH_STR, 1, ord('z') & 0xFF, 0] + [DICT_HAS] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [-1])  # 三值逻辑：假=-1

    def test_dict_keys(self):
        code = [PUSH_STR, 1, ord('x') & 0xFF, 0] + _push_i(99) + _push_i(1) + [DICT]
        code += [DICT_KEYS] + _halt()
        vm = _make_vm(code)
        vm.run()
        self.assertEqual(vm.stack, [['x']])


class TestFunctionOps(unittest.TestCase):
    def test_call_no_args(self):
        # Layout: caller first, func body after HALT
        # [0-2]   CALL 5  (func at byte 5, no STOREs → 0 args)
        # [3-4]   HALT (won't reach here since RET exits frame... actually it will)
        # Wait: after RET, PC returns to after CALL = byte 3. Need HALT there.
        # Actually: CALL 5 pushes call frame, executes func at 5: PUSH_I 99, RET
        # RET returns to byte 3 (HALT). But we also have _push_i(99) + [RET] after HALT.
        # Layout:
        # [0-2]   CALL 5
        # [3]     HALT
        # [4-8]   PUSH_I 99  (func body)
        # [9]     RET
        func_addr = 4
        vm_code = [CALL, func_addr, 0] + _halt() + _push_i(99) + [RET]
        vm = _make_vm(vm_code)
        vm.run()
        self.assertEqual(vm.stack, [99])

    def test_call_one_arg(self):
        # Layout: caller first, func body after HALT
        # [0-4]   PUSH_I 42  (arg)
        # [5-7]   CALL 8
        # [8]     HALT
        # [9-10]  STORE 0   (func entry, 1 STORE → 1 arg)
        # [11-12] LOAD 0
        # [13]    RET
        func_addr = 9
        vm_code = _push_i(42) + [CALL, func_addr, 0] + _halt() + [STORE, 0] + [LOAD, 0] + [RET]
        vm = _make_vm(vm_code)
        vm.run()
        self.assertEqual(vm.stack, [42])

    def test_call_two_args(self):
        # [0-4]   PUSH_I 10  (arg1)
        # [5-9]   PUSH_I 20  (arg2)
        # [10-12] CALL 13
        # [13]    HALT
        # [14-15] STORE 0   (func entry, 2 STOREs → 2 args)
        # [16-17] STORE 1
        # [18-19] LOAD 0
        # [20-21] LOAD 1
        # [22]    ADD
        # [23]    RET
        func_addr = 14
        vm_code = _push_i(10) + _push_i(20) + [CALL, func_addr, 0] + _halt()
        vm_code += [STORE, 0] + [STORE, 1] + [LOAD, 0] + [LOAD, 1] + [ADD] + [RET]
        vm = _make_vm(vm_code)
        vm.run()
        self.assertEqual(vm.stack, [30])

    def test_call_preserves_outer_vars(self):
        # Store 99 in var 0, call func that reads var 0, then verify vars preserved
        # [0-4]   PUSH_I 99  (arg)
        # [5-7]   CALL 8
        # [8]     HALT
        # [9-10]  STORE 0   (func entry, 1 STORE → 1 arg)
        # [11-12] LOAD 0    (reads var 0 in func's copy of vars)
        # [13]    RET
        func_addr = 9
        vm_code = _push_i(99) + [CALL, func_addr, 0] + _halt()
        vm_code += [STORE, 0] + [LOAD, 0] + [RET]
        vm = _make_vm(vm_code)
        vm.run()
        # func receives 99, stores to var 0, loads var 0 → returns 99
        self.assertEqual(vm.stack, [99])


class TestIOOps(unittest.TestCase):
    def test_read_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write('hello vm')
            tmp_path = f.name
        try:
            code = [PUSH_STR, len(tmp_path)]
            for ch in tmp_path:
                code.extend([ord(ch) & 0xFF, 0])
            code += [READ_FILE] + _halt()
            vm = _make_vm(code)
            vm.run()
            self.assertEqual(vm.stack, ['hello vm'])
        finally:
            os.unlink(tmp_path)

    def test_write_file(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'vm_test_write.txt')
        try:
            code = [PUSH_STR, len(tmp_path)]
            for ch in tmp_path:
                code.extend([ord(ch) & 0xFF, 0])
            code += [PUSH_STR, 5]
            for ch in 'hello':
                code.extend([ord(ch) & 0xFF, 0])
            code += [WRITE_FILE] + _halt()
            vm = _make_vm(code)
            vm.run()
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'hello')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestVMEdgeCases(unittest.TestCase):
    def test_empty_code(self):
        vm = _make_vm([])
        vm.run()
        self.assertTrue(vm.halted or vm.pc >= len(vm.code))

    def test_single_halt(self):
        vm = _make_vm([HALT])
        vm.run()
        self.assertTrue(vm.halted)

    def test_nop(self):
        vm = _make_vm([NOP] + _halt())
        vm.run()
        self.assertTrue(vm.halted)

    def test_invalid_bin(self):
        with self.assertRaises((VMError, FileNotFoundError, OSError)):
            VM.from_bin('_nonexistent_test_file_.bin')

    def test_stack_after_run(self):
        vm = _make_vm(_push_i(1) + _push_i(2) + [ADD] + _halt())
        vm.run()
        self.assertEqual(len(vm.stack), 1)
        self.assertEqual(vm.stack[0], 3)


class TestVMUncoveredOps(unittest.TestCase):
    """覆盖之前未测试的 opcode"""

    def test_print(self):
        """PRINT: 输出栈顶值"""
        vm = _make_vm(_push_i(42) + [PRINT] + _halt())
        vm.run()
        self.assertTrue(vm.halted)

    def test_and_op(self):
        """AND: 三态逻辑与"""
        vm = _make_vm(_push_i(1) + _push_i(1) + [AND] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 1)

    def test_io_read(self):
        """IO_READ: 读取设备"""
        vm = _make_vm(_push_i(0) + [IO_READ] + _halt())
        vm.run()
        self.assertTrue(vm.halted)

    def test_io_write(self):
        """IO_WRITE: 写入设备"""
        vm = _make_vm(_push_i(0) + _push_i(0) + [IO_WRITE] + _halt())
        vm.run()
        self.assertTrue(vm.halted)

    def test_str_to_list(self):
        """STR_TO_LIST: 字符串转字符列表"""
        s = 'ab'
        code = [PUSH_STR, len(s)] + [ord(c) for c in s]
        vm = _make_vm(code + [STR_TO_LIST] + _halt())
        vm.run()
        self.assertIsNotNone(vm.stack[0])

    def test_dict_len(self):
        """DICT_LEN: 字典长度"""
        vm = _make_vm(_push_i(0) + [DICT] + [DICT_LEN] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 0)


class TestBitwiseOps(unittest.TestCase):
    """位运算操作码测试"""

    def test_bit_and(self):
        """BIT_AND: 按位与"""
        from vm import BIT_AND

        # 0b1100 & 0b1010 = 0b1000 = 8
        vm = _make_vm(_push_i(12) + _push_i(10) + [BIT_AND] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 8)

    def test_bit_or(self):
        """BIT_OR: 按位或"""
        from vm import BIT_OR

        # 0b1100 | 0b1010 = 0b1110 = 14
        vm = _make_vm(_push_i(12) + _push_i(10) + [BIT_OR] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 14)

    def test_bit_xor(self):
        """BIT_XOR: 按位异或"""
        from vm import BIT_XOR

        # 0b1100 ^ 0b1010 = 0b0110 = 6
        vm = _make_vm(_push_i(12) + _push_i(10) + [BIT_XOR] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 6)

    def test_bit_not(self):
        """BIT_NOT: 按位取反"""
        from vm import BIT_NOT

        # ~0 = -1
        vm = _make_vm(_push_i(0) + [BIT_NOT] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], -1)

    def test_shift_left(self):
        """SHIFT_L: 左移"""
        from vm import SHIFT_L

        # 1 << 3 = 8
        vm = _make_vm(_push_i(1) + _push_i(3) + [SHIFT_L] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 8)

    def test_shift_right(self):
        """SHIFT_R: 右移"""
        from vm import SHIFT_R

        # 8 >> 2 = 2
        vm = _make_vm(_push_i(8) + _push_i(2) + [SHIFT_R] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 2)


class TestStringExtOps(unittest.TestCase):
    """扩展字符串操作码测试"""

    def test_str_contains(self):
        """STR_CONTAINS: 字符串包含"""
        from vm import STR_CONTAINS

        vm = _make_vm(_push_str('hello world') + _push_str('world') + [STR_CONTAINS] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 1)

    def test_str_contains_false(self):
        """STR_CONTAINS: 不包含"""
        from vm import STR_CONTAINS

        vm = _make_vm(_push_str('hello') + _push_str('xyz') + [STR_CONTAINS] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], -1)

    def test_str_startswith(self):
        """STR_STARTSWITH: 字符串前缀"""
        from vm import STR_STARTSWITH

        vm = _make_vm(_push_str('hello world') + _push_str('hello') + [STR_STARTSWITH] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 1)


class TestByteOps(unittest.TestCase):
    """字节操作码测试"""

    def test_hi_byte(self):
        """HI_BYTE: 高字节"""
        from vm import HI_BYTE

        # HI_BYTE is binary op: (value, _) → high byte
        # 0x1234 → 0x12
        vm = _make_vm(_push_i(0x1234) + _push_i(0) + [HI_BYTE] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 0x12)

    def test_lo_byte(self):
        """LO_BYTE: 低字节"""
        from vm import LO_BYTE

        # LO_BYTE is binary op: (value, _) → low byte
        # 0x1234 → 0x34 = 52
        vm = _make_vm(_push_i(0x1234) + _push_i(0) + [LO_BYTE] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 0x34)

    def test_merge_bytes(self):
        """MRG_BYT: 合并字节"""
        from vm import MRG_BYT

        # (0x12, 0x34) → 0x1234
        vm = _make_vm(_push_i(0x12) + _push_i(0x34) + [MRG_BYT] + _halt())
        vm.run()
        self.assertEqual(vm.stack[0], 0x1234)


if __name__ == '__main__':
    unittest.main()
