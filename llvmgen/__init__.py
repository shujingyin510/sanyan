"""三言 → LLVM IR 编译器

用法:
    from llvmgen import compile_file
    compile_file('examples/fizzbuzz.san', 'output.ll')
"""

from llvmgen.compiler import compile_file, compile_source

__all__ = ['compile_file', 'compile_source']
