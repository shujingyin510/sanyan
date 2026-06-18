# name: 线性代数
# keywords: 矩阵, 向量, 线性代数, matrix, vector, linear algebra, 转置, 逆矩阵, 行列式


def matrix_transpose(matrix: list) -> list:
    """矩阵转置"""
    if not matrix:
        return []
    return [[matrix[j][i] for j in range(len(matrix))] for i in range(len(matrix[0]))]


def matrix_multiply(a: list, b: list) -> list:
    """矩阵乘法"""
    if not a or not b:
        return []
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])
    if cols_a != rows_b:
        raise ValueError(f'矩阵维度不匹配: ({rows_a}x{cols_a}) * ({rows_b}x{cols_b})')

    result = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result


def matrix_add(a: list, b: list) -> list:
    """矩阵加法"""
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError('矩阵维度不匹配')
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def matrix_scalar_multiply(matrix: list, scalar: float) -> list:
    """矩阵标量乘法"""
    return [[matrix[i][j] * scalar for j in range(len(matrix[0]))] for i in range(len(matrix))]


def matrix_determinant(matrix: list) -> float:
    """计算矩阵行列式（2x2 或 3x3）"""
    n = len(matrix)
    if n == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    elif n == 3:
        return (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
    else:
        raise ValueError(f'仅支持 2x2 和 3x3 矩阵，当前 {n}x{n}')


def matrix_inverse_2x2(matrix: list) -> list:
    """2x2 矩阵求逆"""
    det = matrix_determinant(matrix)
    if det == 0:
        raise ValueError('矩阵不可逆（行列式为 0）')
    return [
        [matrix[1][1] / det, -matrix[0][1] / det],
        [-matrix[1][0] / det, matrix[0][0] / det],
    ]


def vector_dot(a: list, b: list) -> float:
    """向量点积"""
    if len(a) != len(b):
        raise ValueError('向量维度不匹配')
    return sum(x * y for x, y in zip(a, b))


def vector_cross(a: list, b: list) -> list:
    """向量叉积（3D）"""
    if len(a) != 3 or len(b) != 3:
        raise ValueError('叉积仅支持 3D 向量')
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def vector_norm(v: list) -> float:
    """向量范数（欧几里得距离）"""
    return sum(x**2 for x in v) ** 0.5


def vector_normalize(v: list) -> list:
    """向量归一化"""
    norm = vector_norm(v)
    if norm == 0:
        raise ValueError('零向量无法归一化')
    return [x / norm for x in v]
