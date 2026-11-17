"""Compacidad: conteo de ventanas y acuerdo entre CP-SAT y Pyomo en el modelo extendido."""

import pytest
from academic_timetabling_demo.candidates import build_candidates
from academic_timetabling_demo.db import connect, load_instance
from academic_timetabling_demo.model import build_and_solve
from academic_timetabling_demo.synthetic import generate_case
from academic_timetabling_demo.validate import audit

from timetabling_milp import cpsat_model, pyomo_model
from timetabling_milp.compactness import CompactnessData, Line, count_windows, load_compactness
from timetabling_milp.generator import PRESETS, generate
from timetabling_milp.instance import SolverOptions, load_data

OPTIONS = SolverOptions(time_limit_seconds=60, random_seed=42, threads=1)
GAMMA = 5


def prepare(instance):
    connection = connect(":memory:")
    load_instance(connection, instance)
    assert build_candidates(connection).status == "READY"
    return connection, load_data(connection, instance.config), load_compactness(connection, GAMMA)


def rows(run):
    return [(a.section_id, a.pattern_id, a.room_id) for a in run.result.assignments]


def test_windows_are_the_free_blocks_between_the_first_and_last_class_of_a_line():
    # Bloques 1..5 de un grupo en un día; la alternativa k ocuparía el bloque k.
    line = Line("G1", 1, 1, ((1,), (2,), (3,), (4,), (5,)))
    compact = CompactnessData((line,), GAMMA)

    assert compact.windows([1, 2, 3]) == 0
    assert compact.windows([1, 5]) == 3
    assert compact.windows([2, 4]) == 1
    assert compact.windows([3]) == 0
    assert compact.windows([]) == 0


def test_gamma_must_be_positive():
    with pytest.raises(ValueError):
        load_compactness(connect(":memory:"), 0)


def test_cp_sat_without_compactness_matches_the_original_model():
    instance = generate_case("demo", 42).instance
    connection, data, _ = prepare(instance)

    run = cpsat_model.solve(data, OPTIONS)

    assert run.result.status == "OPTIMAL"
    assert run.result.objective == build_and_solve(connection, instance.config).objective
    assert run.windows is None


@pytest.mark.parametrize(
    "instance",
    [generate_case("demo", 42).instance, generate("small", PRESETS["small"], 1).instance],
    ids=["demo-42", "small-1"],
)
def test_both_paradigms_reach_the_same_optimum_with_compactness(instance):
    _, data, compact = prepare(instance)
    base = pyomo_model.solve(data, OPTIONS)

    runs = [cpsat_model.solve(data, OPTIONS, compact), pyomo_model.solve(data, OPTIONS, compact)]

    assert [run.result.status for run in runs] == ["OPTIMAL", "OPTIMAL"]
    assert runs[0].total == runs[1].total
    for run in runs:
        assert audit(instance, rows(run)).passed
        assert run.windows == count_windows(instance, rows(run))
        assert run.total == run.result.objective + GAMMA * run.windows
        assert run.result.solver_objective == pytest.approx(run.total)
        # El óptimo extendido no puede ser peor que evaluar el horario del modelo base.
        assert run.total <= base.result.objective + GAMMA * count_windows(instance, rows(base))
        # Ni su costo por alternativas puede bajar del óptimo del modelo base.
        assert run.result.objective >= base.result.objective


def test_compactness_weakens_nothing_in_the_relaxation_bound():
    instance = generate("small", PRESETS["small"], 1).instance
    _, data, compact = prepare(instance)

    base = pyomo_model.lp_relaxation(data, OPTIONS)
    extended = pyomo_model.lp_relaxation(data, OPTIONS, compact)

    assert base <= extended + 1e-6
