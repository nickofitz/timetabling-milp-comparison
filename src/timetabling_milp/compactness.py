"""Compacidad: una restricción blanda que acopla secciones.

Una ventana es un bloque libre entre dos bloques ocupados de un mismo grupo en un mismo día
de una misma semana. El modelo base solo tiene costos por alternativa; las ventanas
dependen de qué eligen varias secciones a la vez, así que el objetivo deja de ser separable:

    min  sum_a c_a x_a + gamma * sum_{l,k} v_lk

Para cada línea l = (grupo, semana, día), con y_k = sum de las x que ocupan el bloque k:

    p_k >= y_{k-1},  p_k >= p_{k-1}          p_k: hay clase antes de k
    s_k >= y_{k+1},  s_k >= s_{k+1}          s_k: hay clase después de k
    v_k >= p_k + s_k - 1 - y_k               v_k: k es una ventana

Es una formulación sin big-M. Como se minimiza, p, s y v toman su valor mínimo y v cuenta
exactamente las ventanas.
"""

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from academic_timetabling_demo.domain import Instance


@dataclass(frozen=True)
class Line:
    """Un (grupo, semana, día). `slots[k]` son las alternativas que ocuparían el bloque k,
    contado desde el primer bloque que alguna alternativa puede ocupar hasta el último."""

    group_id: str
    week_id: int
    day_id: int
    slots: tuple[tuple[int, ...], ...]

    @property
    def interior(self) -> range:
        return range(1, len(self.slots) - 1)


@dataclass(frozen=True)
class CompactnessData:
    lines: tuple[Line, ...]
    gamma: int

    def windows(self, chosen: Iterable[int]) -> int:
        """Ventanas de una elección de alternativas, contadas sin pasar por el solver."""
        picked = set(chosen)
        total = 0
        for line in self.lines:
            busy = [
                k for k, alternatives in enumerate(line.slots) if picked.intersection(alternatives)
            ]
            if busy:
                total += busy[-1] - busy[0] + 1 - len(busy)
        return total


def load_compactness(connection: sqlite3.Connection, gamma: int) -> CompactnessData:
    if gamma <= 0:
        raise ValueError("gamma debe ser un entero positivo")
    by_line: dict[tuple[str, int, int], dict[int, tuple[int, ...]]] = defaultdict(dict)
    for group_id, week_id, day_id, block_id, alt_ids in connection.execute(
        "SELECT resource_id, week_id, day_id, block_id, group_concat(alt_id) FROM occupancy "
        "WHERE resource_type = 'group' GROUP BY resource_id, week_id, day_id, block_id"
    ):
        by_line[(group_id, week_id, day_id)][block_id] = tuple(int(a) for a in alt_ids.split(","))
    lines = []
    for (group_id, week_id, day_id), blocks in sorted(by_line.items()):
        slots = tuple(blocks.get(b, ()) for b in range(min(blocks), max(blocks) + 1))
        if len(slots) > 2:  # con dos bloques o menos no cabe una ventana
            lines.append(Line(group_id, week_id, day_id, slots))
    return CompactnessData(tuple(lines), gamma)


def count_windows(instance: Instance, assignments: Iterable[tuple[str, str, str]]) -> int:
    """Conteo independiente: desde la entrada original y el horario, sin tablas derivadas."""
    groups: dict[str, list[str]] = defaultdict(list)
    for membership in instance.section_groups:
        groups[membership.section_id].append(membership.group_id)
    weeks: dict[str, list[int]] = defaultdict(list)
    for active in instance.section_weeks:
        weeks[active.section_id].append(active.week_id)
    sessions: dict[str, list] = defaultdict(list)
    for session in instance.pattern_sessions:
        sessions[session.pattern_id].append(session)

    busy: dict[tuple[str, int, int], set[int]] = defaultdict(set)
    for section_id, pattern_id, _room in assignments:
        for session in sessions[pattern_id]:
            blocks = range(session.start_block_id, session.start_block_id + session.duration_blocks)
            for group_id in groups[section_id]:
                for week_id in weeks[section_id]:
                    busy[(group_id, week_id, session.day_id)].update(blocks)
    return sum(max(blocks) - min(blocks) + 1 - len(blocks) for blocks in busy.values())
