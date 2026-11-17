"""CP-SAT con compacidad opcional.

El modelo CP-SAT del MVP original no admite términos extra en el objetivo y esta carpeta no
lo modifica. Para comparar paradigmas con la restricción de compacidad se necesita, por
tanto, un modelo CP-SAT propio. Sin compacidad equivale al original, que sigue siendo la
referencia en las pruebas.
"""

import math
import time

from ortools.sat.python import cp_model

from timetabling_milp.compactness import CompactnessData
from timetabling_milp.instance import MilpRun, SetPartitioningData, SolverOptions, to_result


def solve(
    data: SetPartitioningData,
    options: SolverOptions,
    compact: CompactnessData | None = None,
) -> MilpRun:
    start = time.perf_counter()
    model = cp_model.CpModel()
    x = {a: model.new_bool_var(f"x{a}") for a in data.alternatives}
    for alternatives in data.by_section.values():
        model.add_exactly_one(x[a] for a in alternatives)
    for clique in data.cliques:
        model.add_at_most_one(x[a] for a in clique)
    objective = sum(data.cost(a) * x[a] for a in data.alternatives)

    if compact is not None:
        windows = []
        for i, line in enumerate(compact.lines):
            y = [sum(x[a] for a in alternatives) for alternatives in line.slots]
            before = {k: model.new_bool_var(f"p{i}_{k}") for k in line.interior}
            after = {k: model.new_bool_var(f"s{i}_{k}") for k in line.interior}
            for k in line.interior:
                model.add(before[k] >= y[k - 1])
                model.add(after[k] >= y[k + 1])
                if k - 1 in before:
                    model.add_implication(before[k - 1], before[k])
                if k + 1 in after:
                    model.add_implication(after[k + 1], after[k])
                window = model.new_bool_var(f"v{i}_{k}")
                model.add(window >= before[k] + after[k] - 1 - y[k])
                windows.append(window)
        objective += compact.gamma * sum(windows)
    model.minimize(objective)
    built = time.perf_counter()

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_seconds
    solver.parameters.random_seed = options.random_seed
    solver.parameters.num_workers = options.threads
    status = solver.status_name(solver.solve(model))
    elapsed = time.perf_counter() - built

    solved = status in ("OPTIMAL", "FEASIBLE")
    chosen = [a for a in x if solver.boolean_value(x[a])] if solved else None
    bound = solver.best_objective_bound if solved else None
    result = to_result(
        data,
        status,
        chosen,
        solver.objective_value if solved else None,
        bound if bound is not None and math.isfinite(bound) else None,
        built - start,
        elapsed,
    )
    return MilpRun("cp-sat", result, compact, None if chosen is None else tuple(chosen))
