from collections.abc import Sequence
from fractions import Fraction


class SingularSystem(ValueError):
    pass


def solve_exact(
    matrix: Sequence[Sequence[Fraction]], rhs: Sequence[Fraction],
) -> tuple[Fraction, ...]:
    size = len(rhs)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError('expected a square coefficient matrix and matching right-hand side')
    rows = [[Fraction(value) for value in row] + [Fraction(result)]
            for row, result in zip(matrix, rhs)]
    for column in range(size):
        pivot_index = next((index for index in range(column, size) if rows[index][column]), None)
        if pivot_index is None:
            raise SingularSystem('coefficient matrix is singular')
        rows[column], rows[pivot_index] = rows[pivot_index], rows[column]
        pivot = rows[column][column]
        pivot_row = rows[column]
        for index in range(column + 1, size):
            row = rows[index]
            if row[column]:
                factor = row[column] / pivot
                for entry in range(column + 1, size + 1):
                    row[entry] -= factor * pivot_row[entry]
                row[column] = Fraction(0)

    solution = [Fraction(0)] * size
    for index in reversed(range(size)):
        row = rows[index]
        remainder = sum((row[column] * solution[column] for column in range(index + 1, size)),
                        Fraction(0))
        solution[index] = (row[-1] - remainder) / row[index]
    return tuple(solution)
