"""Generador de instancias sintéticas de tamaño configurable.

El generador del MVP original solo produce los casos `micro` y `demo` (12 secciones). Este
construye instancias del mismo formato (`Instance`, las 20 tablas) con cualquier tamaño y
con ocupación de salas alta, que es lo que vuelve difícil el problema.

La factibilidad se garantiza con una solución plantada: primero se ubica cada sección en un
(patrón, sala) sin choques y después se derivan de ese testigo la matrícula, las
autorizaciones y las indisponibilidades. El testigo no es óptimo ni se entrega al solver.
"""

import random
from dataclasses import dataclass
from itertools import product

from academic_timetabling_demo.domain import (
    DEFAULT_CONFIG,
    TABLES,
    Block,
    DataValidationError,
    Day,
    Feature,
    Group,
    Instance,
    Pattern,
    PatternSession,
    Room,
    RoomAvailable,
    RoomFeature,
    Row,
    Section,
    SectionFeature,
    SectionGroup,
    SectionPattern,
    SectionWeek,
    Teacher,
    TeacherAvailable,
    TeacherPenalty,
    Week,
    validate_instance,
)
from academic_timetabling_demo.synthetic import GeneratedCase, GenerationError, WitnessAssignment

Slot = tuple[int, int]  # (día, bloque)

_DAY_PAIRS = ((1, 3), (2, 4), (3, 5), (1, 4), (2, 5))
# (sesiones por semana, bloques por sesión) y su peso en la mezcla de secciones.
_SHAPES = (((2, 2), 0.4), ((2, 1), 0.4), ((1, 2), 0.2))
_LAB = "LAB"
_ATTEMPTS = 50


@dataclass(frozen=True)
class Size:
    sections: int
    rooms: int
    teachers: int
    groups: int
    days: int = 5
    blocks: int = 8
    weeks: int = 1
    extra_patterns: int = 5  # patrones autorizados por sección, además del plantado


# Ocupación de salas aproximada: 70 %, 80 % y 82 % de las franjas.
PRESETS = {
    "small": Size(sections=30, rooms=3, teachers=10, groups=6),
    "medium": Size(sections=80, rooms=7, teachers=26, groups=14),
    "large": Size(sections=200, rooms=17, teachers=66, groups=34),
}


@dataclass(frozen=True)
class _Shape:
    id: str
    sessions: tuple[tuple[int, int, int], ...]  # (día, bloque inicial, duración)

    def slots(self) -> list[Slot]:
        return [(day, start + k) for day, start, length in self.sessions for k in range(length)]


def _catalog(size: Size) -> dict[tuple[int, int], list[_Shape]]:
    days = range(1, size.days + 1)
    blocks = range(1, size.blocks + 1)
    double_starts = range(1, size.blocks, 2)
    pairs = [pair for pair in _DAY_PAIRS if pair[1] <= size.days]
    return {
        (1, 2): [_Shape(f"P1X2-D{d}-B{b}", ((d, b, 2),)) for d, b in product(days, double_starts)],
        (2, 1): [
            _Shape(f"P2X1-D{d1}{d2}-B{b}", ((d1, b, 1), (d2, b, 1)))
            for (d1, d2), b in product(pairs, blocks)
        ],
        (2, 2): [
            _Shape(f"P2X2-D{d1}{d2}-B{b}", ((d1, b, 2), (d2, b, 2)))
            for (d1, d2), b in product(pairs, double_starts)
        ],
    }


def generate(name: str, size: Size, seed: int) -> GeneratedCase:
    """Genera una instancia válida y factible; reintenta el testigo con otras subsemillas."""
    for attempt in range(_ATTEMPTS):
        built = _build(size, random.Random(f"{name}-{seed}-{attempt}"))
        if built is not None:
            instance, witness = built
            issues = validate_instance(instance)
            if issues:
                raise GenerationError(str(DataValidationError(issues)))
            return GeneratedCase(name, seed, instance, witness)
    raise GenerationError(f"no se pudo plantar un horario para {name} tras {_ATTEMPTS} intentos")


def _build(size: Size, rng: random.Random) -> tuple[Instance, tuple[WitnessAssignment, ...]] | None:
    catalog = _catalog(size)
    weeks = list(range(1, size.weeks + 1))
    all_slots: list[Slot] = list(product(range(1, size.days + 1), range(1, size.blocks + 1)))
    teachers = [f"T{i:03d}" for i in range(1, size.teachers + 1)]
    groups = [f"G{i:02d}" for i in range(1, size.groups + 1)]
    capacities = {f"R{i:02d}": rng.choice((30, 40, 50, 60, 80)) for i in range(1, size.rooms + 1)}
    labs = set(rng.sample(sorted(capacities), max(1, size.rooms // 5)))

    kinds = rng.choices([s for s, _ in _SHAPES], [w for _, w in _SHAPES], k=size.sections)
    # Las secciones que ocupan más franjas se plantan primero: son las más difíciles de ubicar.
    order = sorted(range(size.sections), key=lambda i: -kinds[i][0] * kinds[i][1])
    busy: set[tuple[str, str, Slot]] = set()
    room_slots: dict[str, set[Slot]] = {room: set() for room in capacities}
    teacher_slots: dict[str, set[Slot]] = {teacher: set() for teacher in teachers}

    sections, section_groups, section_features, section_patterns = [], [], [], []
    witness, used = [], {}
    for index in order:
        section_id = f"S{index + 1:03d}"
        teacher = teachers[index % len(teachers)]
        members = [groups[index % len(groups)]]
        if index % 4 == 0:
            members.append(groups[(index + 1) % len(groups)])
        shapes = catalog[kinds[index]]
        options = list(product(shapes, capacities))
        rng.shuffle(options)
        for shape, room in options:
            resources = [("room", room), ("teacher", teacher), *(("group", g) for g in members)]
            occupied = {(kind, name, slot) for kind, name in resources for slot in shape.slots()}
            if not occupied & busy:
                busy |= occupied
                break
        else:
            return None

        room_slots[room] |= set(shape.slots())
        teacher_slots[teacher] |= set(shape.slots())
        witness.append(WitnessAssignment(section_id, shape.id, room))
        sections.append(
            Section(
                id=section_id,
                name=f"Sección {index + 1:03d}",
                teacher_id=teacher,
                enrollment=rng.randint(capacities[room] // 2, capacities[room]),
                sessions_per_week=kinds[index][0],
                blocks_per_session=kinds[index][1],
            )
        )
        section_groups += [SectionGroup(section_id=section_id, group_id=g) for g in members]
        if room in labs and rng.random() < 0.5:
            section_features.append(SectionFeature(section_id=section_id, feature_id=_LAB))
        others = [candidate for candidate in shapes if candidate.id != shape.id]
        authorized = [shape, *rng.sample(others, min(size.extra_patterns, len(others)))]
        section_patterns += [
            SectionPattern(section_id=section_id, pattern_id=p.id) for p in authorized
        ]
        used.update({p.id: p for p in authorized})

    teacher_available, teacher_penalties = [], []
    for teacher in teachers:
        free = [slot for slot in all_slots if slot not in teacher_slots[teacher]]
        unavailable = set(rng.sample(free, min(4, len(free))))
        teacher_available += [
            TeacherAvailable(teacher_id=teacher, week_id=w, day_id=d, block_id=b)
            for w, (d, b) in product(weeks, all_slots)
            if (d, b) not in unavailable
        ]
        teacher_penalties += [
            TeacherPenalty(teacher_id=teacher, day_id=d, block_id=b, penalty=rng.randint(1, 5))
            for d, b in rng.sample(all_slots, 8)
        ]
    room_available = []
    for room in capacities:
        free = [slot for slot in all_slots if slot not in room_slots[room]]
        unavailable = set(rng.sample(free, min(2, len(free))))
        room_available += [
            RoomAvailable(room_id=room, week_id=w, day_id=d, block_id=b)
            for w, (d, b) in product(weeks, all_slots)
            if (d, b) not in unavailable
        ]

    tables: dict[str, list[Row]] = {
        "weeks": [Week(id=w) for w in weeks],
        "days": [Day(id=d) for d in range(1, size.days + 1)],
        "blocks": [
            Block(id=b, start_time=f"{7 + b:02d}:00", end_time=f"{8 + b:02d}:00")
            for b in range(1, size.blocks + 1)
        ],
        "teachers": [Teacher(id=t, name=f"Docente {t[1:]}") for t in teachers],
        "rooms": [Room(id=r, name=f"Sala {r[1:]}", capacity=c) for r, c in capacities.items()],
        "features": [Feature(id=_LAB, name="Laboratorio")],
        "room_features": [RoomFeature(room_id=r, feature_id=_LAB) for r in labs],
        "groups": [Group(id=g, name=f"Grupo {g[1:]}", basis="regla_curricular") for g in groups],
        "sections": sections,
        "section_groups": section_groups,
        "section_features": section_features,
        "section_weeks": [SectionWeek(section_id=s.id, week_id=w) for s in sections for w in weeks],
        "patterns": [Pattern(id=p.id, name=p.id) for p in used.values()],
        "pattern_sessions": [
            PatternSession(
                pattern_id=p.id, session_id=str(n), day_id=d, start_block_id=b, duration_blocks=k
            )
            for p in used.values()
            for n, (d, b, k) in enumerate(p.sessions, start=1)
        ],
        "section_patterns": section_patterns,
        "teacher_available": teacher_available,
        "room_available": room_available,
        "teacher_penalties": teacher_penalties,
    }
    ordered = {
        spec.name: tuple(
            sorted(
                tables.get(spec.name, []), key=lambda r: tuple(getattr(r, c) for c in spec.columns)
            )
        )
        for spec in TABLES
    }
    return Instance(config=DEFAULT_CONFIG, **ordered), tuple(witness)
