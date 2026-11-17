"""Los backends MILP deben coincidir con CP-SAT en estado y valor objetivo.

Las asignaciones pueden diferir entre solvers cuando hay óptimos alternativos; por eso se
compara el objetivo y se exige que cada horario pase el auditor independiente del MVP.
"""

import pytest
from academic_timetabling_demo.candidates import build_candidates
from academic_timetabling_demo.db import connect, load_instance
from academic_timetabling_demo.model import Alternative, build_and_solve
from academic_timetabling_demo.synthetic import generate_case
from academic_timetabling_demo.validate import audit

from timetabling_milp import pulp_model, pyomo_model
from timetabling_milp.instance import SetPartitioningData, SolverOptions, load_data

OPTIONS = SolverOptions(time_limit_seconds=30, random_seed=42, threads=1)
BACKENDS = {
    "pyomo+highs": lambda data: pyomo_model.solve(data, OPTIONS),
    "pulp+highs": lambda data: pulp_model.solve(data, OPTIONS, "highs"),
    "pulp+cbc": lambda data: pulp_model.solve(data, OPTIONS, "cbc"),
}
CASES = [("micro", 0)] + [("demo", seed) for seed in (1, 7, 42, 2026)]


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(("case", "seed"), CASES)
def test_backend_matches_cp_sat(case, seed, backend):
    instance = generate_case(case, seed).instance
    connection = connect(":memory:")
    load_instance(connection, instance)
    assert build_candidates(connection).status == "READY"
    reference = build_and_solve(connection, instance.config)
    data = load_data(connection, instance.config)

    run = BACKENDS[backend](data)

    assert reference.status == "OPTIMAL"
    assert run.result.status == "OPTIMAL"
    assert run.result.objective == reference.objective
    rows = [(a.section_id, a.pattern_id, a.room_id) for a in run.result.assignments]
    assert audit(instance, rows, run.result.objective).passed


@pytest.mark.parametrize(("case", "seed"), CASES)
def test_lp_relaxation_is_a_lower_bound(case, seed):
    instance = generate_case(case, seed).instance
    connection = connect(":memory:")
    load_instance(connection, instance)
    build_candidates(connection)
    data = load_data(connection, instance.config)

    bound = pyomo_model.lp_relaxation(data, OPTIONS)
    optimum = pyomo_model.solve(data, OPTIONS).result.objective

    assert bound is not None
    assert bound <= optimum + 1e-6


@pytest.mark.parametrize("backend", BACKENDS)
def test_two_sections_fighting_for_one_slot_are_infeasible(backend):
    data = SetPartitioningData(
        alternatives={
            1: Alternative(1, "S1", "P1", "R1", 0, 0),
            2: Alternative(2, "S2", "P1", "R1", 0, 0),
        },
        by_section={"S1": (1,), "S2": (2,)},
        cliques=((1, 2),),
        alpha=10,
        beta=1,
    )

    run = BACKENDS[backend](data)

    assert run.result.status == "INFEASIBLE"
    assert run.result.assignments == ()
