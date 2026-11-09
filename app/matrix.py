"""Ordenación estratigráfica (diagrama de Harris) a partir de las relaciones «cubre a»."""


class CycleError(ValueError):
    """Hay una contradicción estratigráfica: A cubre a B y, directa o indirectamente, B cubre a A."""

    def __init__(self, units: list[int]):
        self.units = sorted(units)
        super().__init__(f"Contradicción estratigráfica entre las UE: {self.units}")


def compute_levels(nodes: list[int], edges: list[tuple[int, int]]) -> list[list[int]]:
    """Devuelve las UE agrupadas por nivel: el nivel 0 son las más recientes (nadie las cubre).

    `edges` contiene pares (superior, inferior): la superior cubre a la inferior.
    """
    covered_by = {n: 0 for n in nodes}
    below: dict[int, list[int]] = {n: [] for n in nodes}
    for upper, lower in edges:
        below[upper].append(lower)
        covered_by[lower] += 1

    level = sorted(n for n, count in covered_by.items() if count == 0)
    levels: list[list[int]] = []
    seen = 0
    while level:
        levels.append(level)
        seen += len(level)
        nxt: list[int] = []
        for n in level:
            for lower in below[n]:
                covered_by[lower] -= 1
                if covered_by[lower] == 0:
                    nxt.append(lower)
        level = sorted(nxt)

    if seen != len(nodes):
        raise CycleError([n for n, count in covered_by.items() if count > 0])
    return levels
