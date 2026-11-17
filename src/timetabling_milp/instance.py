"""Datos del modelo, independientes de la librería de modelado.

El contrato con el MVP original son sus tablas derivadas `alternative` y `occupancy`.
Con ellas el problema queda reducido a un set partitioning con conflictos:

    min  sum_a c_a x_a
    s.a. sum_{a in A_s} x_a  = 1     para cada sección s          (asignación)
         sum_{a in K_q} x_a <= 1     para cada ocupación q        (conflicto)
         x_a en {0, 1}

con c_a = alpha * D_a + beta * E_a. K_q es el conjunto de alternativas que usan la
ocupación q (recurso, semana, día, bloque): cada restricción de conflicto es una clique
completa, la versión más fuerte posible para la relajación lineal.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from academic_timetabling_demo.domain import RunConfig
from academic_timetabling_demo.model import Alternative, Assignment, ModelError, SolveResult

if TYPE_CHECKING:
    from timetabling_milp.compactness import CompactnessData


@dataclass(frozen=True)
class SetPartitioningData:
    alternatives: dict[int, Alternative]
    by_section: dict[str, tuple[int, ...]]
    cliques: tuple[tuple[int, ...], ...]
    alpha: int
    beta: int

    def cost(self, alt_id: int) -> int:
        alternative = self.alternatives[alt_id]
        return self.alpha * alternative.cost_d + self.beta * alternative.cost_e


@dataclass(frozen=True)
class SolverOptions:
    time_limit_seconds: float
    random_seed: int
    threads: int

    @classmethod
    def from_config(cls, config: RunConfig) -> "SolverOptions":
        return cls(float(config.time_limit_seconds), config.random_seed, config.num_search_workers)


@dataclass(frozen=True)
class MilpRun:
    """Resultado de un backend, en el mismo `SolveResult` que usa el modelo CP-SAT.

    Con compacidad, `result.objective` sigue siendo el costo de las alternativas, mientras
    que `result.solver_objective` y `result.best_bound` se refieren al objetivo completo.
    """

    backend: str
    result: SolveResult
    compact: "CompactnessData | None" = None
    chosen: tuple[int, ...] | None = None

    @property
    def windows(self) -> int | None:
        """Ventanas del horario; solo se calcula cuando el modelo incluye compacidad."""
        if self.compact is None or self.chosen is None:
            return None
        return self.compact.windows(self.chosen)

    @property
    def total(self) -> int | None:
        """Objetivo completo, reconstruido: costos de las alternativas más gamma * ventanas."""
        if self.result.objective is None:
            return None
        return self.result.objective + (self.compact.gamma * self.windows if self.compact else 0)


def load_data(connection: sqlite3.Connection, config: RunConfig) -> SetPartitioningData:
    """Lee las mismas tablas, con las mismas consultas, que el modelo CP-SAT original."""
    alternatives = {
        row[0]: Alternative(*row)
        for row in connection.execute(
            "SELECT alt_id, section_id, pattern_id, room_id, cost_d, cost_e "
            "FROM alternative ORDER BY alt_id"
        )
    }
    by_section: dict[str, list[int]] = defaultdict(list)
    for alternative in alternatives.values():
        by_section[alternative.section_id].append(alternative.alt_id)
    for (section_id,) in connection.execute("SELECT id FROM sections ORDER BY id"):
        if not by_section[section_id]:
            raise ModelError(
                f"la sección {section_id} no tiene alternativas: el precheck debió detenerse"
            )
    cliques = tuple(
        tuple(int(alt_id) for alt_id in alt_ids.split(","))
        for (alt_ids,) in connection.execute(
            "SELECT group_concat(alt_id) FROM occupancy "
            "GROUP BY resource_type, resource_id, week_id, day_id, block_id "
            "HAVING count(*) > 1"
        )
    )
    return SetPartitioningData(
        alternatives=alternatives,
        by_section={section: tuple(ids) for section, ids in sorted(by_section.items())},
        cliques=cliques,
        alpha=config.alpha,
        beta=config.beta,
    )


def to_result(
    data: SetPartitioningData,
    status: str,
    chosen: list[int] | None,
    solver_objective: float | None,
    best_bound: float | None,
    build_seconds: float,
    solve_seconds: float,
) -> SolveResult:
    """Traduce la salida de un solver MILP al `SolveResult` del MVP original.

    Como en el original, `objective` se reconstruye desde los costos enteros de las
    alternativas elegidas; `solver_objective` es lo que informó el solver.
    """
    picked = sorted(
        (data.alternatives[alt_id] for alt_id in chosen or ()), key=lambda a: a.section_id
    )
    solved = chosen is not None
    return SolveResult(
        status=status,
        objective=sum(data.cost(a.alt_id) for a in picked) if solved else None,
        cost_d=sum(a.cost_d for a in picked) if solved else None,
        cost_e=sum(a.cost_e for a in picked) if solved else None,
        solver_objective=solver_objective if solved else None,
        best_bound=best_bound,
        assignments=tuple(Assignment(a.section_id, a.pattern_id, a.room_id) for a in picked),
        num_variables=len(data.alternatives),
        num_constraints=len(data.by_section) + len(data.cliques),
        num_conflict_constraints=len(data.cliques),
        build_seconds=build_seconds,
        solve_seconds=solve_seconds,
    )
