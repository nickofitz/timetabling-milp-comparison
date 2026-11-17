"""El generador produce instancias válidas, factibles y reproducibles."""

import pytest
from academic_timetabling_demo.candidates import build_candidates
from academic_timetabling_demo.db import connect, load_instance
from academic_timetabling_demo.domain import validate_instance
from academic_timetabling_demo.validate import audit

from timetabling_milp.generator import PRESETS, generate


@pytest.mark.parametrize("name", PRESETS)
def test_instance_is_valid_and_its_witness_is_a_feasible_timetable(name):
    case = generate(name, PRESETS[name], seed=1)
    witness = [(w.section_id, w.pattern_id, w.room_id) for w in case.witness]

    assert validate_instance(case.instance) == []
    assert len(case.instance.sections) == PRESETS[name].sections
    assert audit(case.instance, witness).passed


def test_every_section_keeps_at_least_one_alternative_after_the_sql_prefilter():
    case = generate("small", PRESETS["small"], seed=1)
    connection = connect(":memory:")
    load_instance(connection, case.instance)

    assert build_candidates(connection).status == "READY"


def test_same_seed_gives_the_same_instance_and_another_seed_a_different_one():
    size = PRESETS["small"]

    assert generate("small", size, 7).instance == generate("small", size, 7).instance
    assert generate("small", size, 7).instance != generate("small", size, 8).instance
