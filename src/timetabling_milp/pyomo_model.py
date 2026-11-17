"""La formulación en Pyomo, resuelta con HiGHS.

Pyomo es un lenguaje de modelado algebraico: el modelo se declara con conjuntos,
parámetros, variables y restricciones indexadas, como en la notación matemática, y queda
separado del solver. Aquí además se aprovecha esa separación para resolver la relajación
lineal del mismo modelo sin reescribirlo.
"""

import time

import pyomo.environ as pyo
from pyomo.contrib.appsi.base import TerminationCondition
from pyomo.contrib.appsi.solvers import Highs

from timetabling_milp.compactness import CompactnessData
from timetabling_milp.instance import MilpRun, SetPartitioningData, SolverOptions, to_result

_STATUS = {
    TerminationCondition.optimal: "OPTIMAL",
    TerminationCondition.infeasible: "INFEASIBLE",
}


def build(data: SetPartitioningData) -> pyo.ConcreteModel:
    model = pyo.ConcreteModel(name="timetabling")
    model.A = pyo.Set(initialize=list(data.alternatives), doc="alternativas admisibles")
    model.S = pyo.Set(initialize=list(data.by_section), doc="secciones")
    model.Q = pyo.Set(initialize=range(len(data.cliques)), doc="ocupaciones en disputa")
    model.c = pyo.Param(model.A, initialize=lambda _, a: data.cost(a), doc="alpha * D + beta * E")
    model.x = pyo.Var(model.A, domain=pyo.Binary)

    @model.Constraint(model.S)
    def assignment(m, s):
        return sum(m.x[a] for a in data.by_section[s]) == 1

    @model.Constraint(model.Q)
    def conflict(m, q):
        return sum(m.x[a] for a in data.cliques[q]) <= 1

    model.cost = pyo.Objective(expr=pyo.sum_product(model.c, model.x), sense=pyo.minimize)
    return model


def add_compactness(model: pyo.ConcreteModel, compact: CompactnessData) -> None:
    """Extiende un modelo ya construido con un bloque de compacidad y un objetivo nuevo.

    Las variables auxiliares son continuas en [0, 1]: con x binaria, su valor mínimo ya es
    0 o 1, así que declararlas enteras solo agrandaría el árbol de búsqueda.
    """
    block = model.compact = pyo.Block()
    block.K = pyo.Set(
        dimen=2, initialize=[(i, k) for i, line in enumerate(compact.lines) for k in line.interior]
    )
    block.before = pyo.Var(block.K, domain=pyo.UnitInterval)
    block.after = pyo.Var(block.K, domain=pyo.UnitInterval)
    block.window = pyo.Var(block.K, domain=pyo.UnitInterval)

    def busy(i, k):
        return sum(model.x[a] for a in compact.lines[i].slots[k])

    block.links = pyo.ConstraintList()
    for i, k in block.K:
        block.links.add(block.before[i, k] >= busy(i, k - 1))
        block.links.add(block.after[i, k] >= busy(i, k + 1))
        if (i, k - 1) in block.K:
            block.links.add(block.before[i, k] >= block.before[i, k - 1])
        if (i, k + 1) in block.K:
            block.links.add(block.after[i, k] >= block.after[i, k + 1])
        block.links.add(
            block.window[i, k] >= block.before[i, k] + block.after[i, k] - 1 - busy(i, k)
        )

    model.cost.deactivate()
    model.total = pyo.Objective(
        expr=model.cost.expr + compact.gamma * pyo.summation(block.window), sense=pyo.minimize
    )


def _solver(options: SolverOptions) -> Highs:
    solver = Highs()
    solver.config.load_solution = False
    solver.config.time_limit = options.time_limit_seconds
    solver.highs_options = {"random_seed": options.random_seed, "threads": options.threads}
    return solver


def solve(
    data: SetPartitioningData,
    options: SolverOptions,
    compact: CompactnessData | None = None,
) -> MilpRun:
    start = time.perf_counter()
    model = build(data)
    if compact is not None:
        add_compactness(model, compact)
    built = time.perf_counter()
    results = _solver(options).solve(model)
    elapsed = time.perf_counter() - built

    has_solution = results.best_feasible_objective is not None
    status = _STATUS.get(results.termination_condition, "FEASIBLE" if has_solution else "UNKNOWN")
    chosen = None
    if has_solution:
        results.solution_loader.load_vars()
        chosen = [a for a in model.A if pyo.value(model.x[a]) > 0.5]
    bound = results.best_objective_bound if status != "INFEASIBLE" else None
    result = to_result(
        data, status, chosen, results.best_feasible_objective, bound, built - start, elapsed
    )
    return MilpRun("pyomo+highs", result, compact, None if chosen is None else tuple(chosen))


def lp_relaxation(
    data: SetPartitioningData,
    options: SolverOptions,
    compact: CompactnessData | None = None,
) -> float | None:
    """Valor óptimo de la relajación lineal (x en [0, 1]); None si no se resolvió."""
    model = build(data)
    if compact is not None:
        add_compactness(model, compact)
    pyo.TransformationFactory("core.relax_integer_vars").apply_to(model)
    results = _solver(options).solve(model)
    if results.termination_condition != TerminationCondition.optimal:
        return None
    return results.best_feasible_objective
