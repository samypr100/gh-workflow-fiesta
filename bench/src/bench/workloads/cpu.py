"""A CPU-bound kernel expressed entirely in Python bytecode.

Standard library only. This module is imported by the target interpreter,
which has no third-party packages installed.

The arithmetic is deliberately written as interpreted operations rather than
delegated to a C routine. A kernel that spent its time inside C would release
the GIL and make GIL-enabled and free-threaded builds look identical, which
would defeat the purpose of the comparison.
"""

MODULUS = 1_000_003
MULTIPLIER = 31
OPERATIONS_PER_ITERATION = 1


def cpu_chunk(iterations: int) -> int:
    """Run a fixed amount of interpreted arithmetic.

    Args:
        iterations: Number of arithmetic rounds to perform.

    Returns:
        An accumulator whose value depends on the iteration count, returned so
        the loop cannot be optimised away.
    """
    total = 0
    for index in range(iterations):
        total = (total * MULTIPLIER + index * index) % MODULUS
    return total
