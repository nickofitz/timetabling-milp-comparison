"""La misma formulación en PuLP, resuelta con HiGHS o con CBC.

PuLP es un modelador más directo: el problema se arma sumando expresiones a un
`LpProblem`. No tiene conjuntos ni parámetros propios; los índices son estructuras de
Python. Desde PuLP 4, CBC ya no viene incluido: se instala con el extra `pulp[cbc]`.
"""

import time

import pulp

from timetabling_milp.instance import MilpRun, SetPartitioningData, SolverOptions, to_result


def build(data: SetPartitioningData) -> tuple[pulp.LpProblem, dict[int, pulp.LpVariable]]:
    problem = pulp.LpProblem("timetabling", pulp.LpMinimize)
    x = problem.add_variable_dicts("x", list(data.alternatives), cat="Binary")
    problem += pulp.lpSum(data.cost(a) * x[a] for a in data.alternatives)
    for index, alternatives in enumerate(data.by_section.values()):
        problem += pulp.lpSum(x[a] for a in alternatives) == 1, f"assignment_{index}"
    for index, clique in enumerate(data.cliques):
        problem += pulp.lpSum(x[a] for a in clique) <= 1, f"conflict_{index}"
    return problem, x


def _solver(name: str, options: SolverOptions) -> pulp.LpSolver:
    common = {"msg": False, "timeLimit": options.time_limit_seconds, "threads": options.threads}
    if name == "highs":
        return pulp.HiGHS(random_seed=options.random_seed, **common)
    if name == "cbc":
        return pulp.COIN_CMD(randomSeed=options.random_seed, **common)
    raise ValueError(f"solver desconocido: {name}")


def solve(data: SetPartitioningData, options: SolverOptions, solver: str = "highs") -> MilpRun:
    start = time.perf_counter()
    problem, x = build(data)
    built = time.perf_counter()
    stats = problem.solve(_solver(solver, options))
    elapsed = time.perf_counter() - built

    if stats.status == pulp.LpSolveStatus.Optimal:
        status = "OPTIMAL"
    elif stats.status == pulp.LpSolveStatus.Infeasible:
        status = "INFEASIBLE"
    else:
        status = "FEASIBLE" if stats.has_solution else "UNKNOWN"
    chosen = None
    if stats.has_solution:
        chosen = [a for a, variable in x.items() if (variable.value() or 0) > 0.5]
    result = to_result(
        data, status, chosen, stats.objective, stats.best_bound, built - start, elapsed
    )
    return MilpRun(f"pulp+{solver}", result)
