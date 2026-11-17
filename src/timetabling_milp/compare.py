"""Compara voraz, CP-SAT, Pyomo y PuLP sobre las mismas instancias.

    uv run python -m timetabling_milp.compare --out docs/comparacion.md

Por cada instancia se resuelven dos modelos:

- Base: el del MVP original (costos por alternativa). Voraz y CP-SAT son los del original.
- Con compacidad: el base más gamma por ventana. CP-SAT y Pyomo, ambos de esta carpeta.

Todos los backends reciben las mismas alternativas y ocupaciones. Cada horario se audita con
el validador independiente del original y sus ventanas se cuentan desde la entrada.
"""

import argparse
import json
from pathlib import Path

from academic_timetabling_demo.baseline import run_greedy
from academic_timetabling_demo.candidates import build_candidates
from academic_timetabling_demo.db import connect, load_instance
from academic_timetabling_demo.domain import Instance
from academic_timetabling_demo.model import build_and_solve
from academic_timetabling_demo.synthetic import CASES, generate_case
from academic_timetabling_demo.validate import audit

from timetabling_milp import cpsat_model, pulp_model, pyomo_model
from timetabling_milp.compactness import count_windows, load_compactness
from timetabling_milp.generator import PRESETS, generate
from timetabling_milp.instance import MilpRun, SolverOptions, load_data

DEFAULT_CASES = ("micro:0", "demo:42", "small:1", "medium:1", "large:1")
Rows = list[tuple[str, str, str]]


def load_case(name: str, seed: int) -> Instance:
    if name in CASES:
        return generate_case(name, seed).instance
    if name in PRESETS:
        return generate(name, PRESETS[name], seed).instance
    raise ValueError(f"caso desconocido: {name}; opciones: {', '.join((*CASES, *PRESETS))}")


def _gap(value: float | None, bound: float | None) -> float | None:
    if value is None or bound is None or value <= 0:
        return None
    return max(0.0, (value - bound) / value)


def _row(instance: Instance, backend: str, status: str, value, bound, rows: Rows | None, **more):
    """Fila del informe. `rows` es None cuando no hay un horario completo que auditar."""
    return {
        "backend": backend,
        "status": status,
        "value": value,
        "bound": bound,
        "gap": _gap(value, bound),
        "audit": None if rows is None else ("PASSED" if audit(instance, rows).passed else "FAILED"),
        "windows": None if rows is None else count_windows(instance, rows),
        **more,
    }


def _exact_row(instance: Instance, run: MilpRun) -> dict:
    result = run.result
    rows = [(a.section_id, a.pattern_id, a.room_id) for a in result.assignments] or None
    row = _row(
        instance, run.backend, result.status, run.total, result.best_bound, rows,
        cost=result.objective, build_seconds=result.build_seconds,
        solve_seconds=result.solve_seconds,
    )  # fmt: skip
    if run.windows is not None and run.windows != row["windows"]:
        row["audit"] = "FAILED"  # el conteo del modelo contradice el conteo independiente
    return row


def compare_case(name: str, seed: int, time_limit: float, gamma: int, threads: int) -> dict:
    instance = load_case(name, seed)
    config = instance.config.model_copy(
        update={"time_limit_seconds": time_limit, "num_search_workers": threads}
    )
    options = SolverOptions.from_config(config)
    connection = connect(":memory:")
    try:
        load_instance(connection, instance)
        precheck = build_candidates(connection)
        if precheck.status != "READY":
            raise RuntimeError(f"{name}:{seed} no está lista para resolver: {precheck.status}")
        data = load_data(connection, config)
        compact = load_compactness(connection, gamma)

        greedy = run_greedy(connection, config)
        complete = greedy.status == "COMPLETE"
        greedy_rows = [(c.section_id, c.pattern_id, c.room_id) for c in greedy.assignments]
        base = [
            _row(
                instance, "voraz", greedy.status, greedy.objective if complete else None, None,
                greedy_rows if complete else None, cost=greedy.objective if complete else None,
                build_seconds=0.0, solve_seconds=greedy.seconds,
                placed=f"{len(greedy_rows)}/{len(data.by_section)}",
            ),
            _exact_row(instance, MilpRun("cp-sat", build_and_solve(connection, config))),
            _exact_row(instance, pyomo_model.solve(data, options)),
            _exact_row(instance, pulp_model.solve(data, options, "highs")),
            _exact_row(instance, pulp_model.solve(data, options, "cbc")),
        ]  # fmt: skip
        compacted = [
            _exact_row(instance, cpsat_model.solve(data, options, compact)),
            _exact_row(instance, pyomo_model.solve(data, options, compact)),
        ]
        return {
            "case": name,
            "seed": seed,
            "time_limit": time_limit,
            "gamma": gamma,
            "threads": threads,
            "sections": len(data.by_section),
            "variables": len(data.alternatives),
            "conflict_constraints": len(data.cliques),
            "compactness_lines": len(compact.lines),
            "lp_base": pyomo_model.lp_relaxation(data, options),
            "lp_compact": pyomo_model.lp_relaxation(data, options, compact),
            "base": base,
            "compact": compacted,
        }
    finally:
        connection.close()


def _fmt(value, pattern: str = "{:.0f}") -> str:
    return "—" if value is None else pattern.format(value)


def _table(rows: list[dict], with_cost: bool) -> list[str]:
    head = "| Backend | Estado | Objetivo | Cota | Brecha |"
    head += " Costo | Ventanas |" if with_cost else " Ventanas |"
    lines = [
        head + " Auditoría | Resolución (s) |",
        "|---|---|---:|---:|---:|" + "---:|" * (2 if with_cost else 1) + "---|---:|",
    ]
    for row in rows:
        status = row["status"] + (f" ({row['placed']})" if row.get("placed") else "")
        cells = [row["backend"], status, _fmt(row["value"]), _fmt(row["bound"], "{:.1f}"),
                 _fmt(row["gap"], "{:.1%}")]  # fmt: skip
        if with_cost:
            cells.append(_fmt(row["cost"]))
        cells += [_fmt(row["windows"]), row["audit"] or "—", f"{row['solve_seconds']:.2f}"]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def to_markdown(results: list[dict], time_limit: float, gamma: int, threads: int) -> str:
    lines = [
        "# Comparación de backends",
        "",
        f"Generado por `timetabling_milp.compare`. Límite de {time_limit:g} s por resolución, "
        f"{threads} hilo(s) por solver, una ejecución por backend. Datos sintéticos.",
        "",
        "- **Objetivo**: reconstruido desde el horario, no el que informa el solver.",
        "- **Cota** y **brecha**: mejor cota inferior del solver y (objetivo − cota) / objetivo.",
        "- **Ventanas**: bloques libres entre clases de un grupo, contados desde la entrada.",
        "- **Voraz** `INCOMPLETE (n/m)`: se atascó tras ubicar n de m secciones; no hay horario.",
        "",
    ]
    for item in results:
        lines += [
            f"## {item['case']} (semilla {item['seed']})",
            "",
            f"{item['sections']} secciones, {item['variables']} variables binarias, "
            f"{item['conflict_constraints']} restricciones de conflicto.",
            "",
            f"### Modelo base (relajación lineal: {_fmt(item['lp_base'], '{:.2f}')})",
            "",
            *_table(item["base"], with_cost=False),
            "",
            f"### Con compacidad, gamma = {gamma} "
            f"(relajación lineal: {_fmt(item['lp_compact'], '{:.2f}')})",
            "",
            *_table(item["compact"], with_cost=True),
            "",
        ]
    return "\n".join(lines)


def consistent(results: list[dict]) -> bool:
    """Ningún horario falla la auditoría y los óptimos demostrados de un modelo coinciden."""
    for item in results:
        for rows in (item["base"], item["compact"]):
            if any(row["audit"] == "FAILED" for row in rows):
                return False
            if len({row["value"] for row in rows if row["status"] == "OPTIMAL"}) > 1:
                return False
    return True


def _key(item: dict) -> tuple:
    return item["case"], item["seed"], item["time_limit"], item["gamma"], item["threads"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES, metavar="CASO:SEMILLA")
    parser.add_argument("--time-limit", type=float, default=20.0, help="segundos por resolución")
    parser.add_argument("--gamma", type=int, default=5, help="costo de cada ventana")
    parser.add_argument("--threads", type=int, default=1, help="hilos o workers por solver")
    parser.add_argument("--out", type=Path, default=None, help="archivo .md; el .json va al lado")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reutiliza del .json existente los casos ya resueltos con el mismo límite y gamma",
    )
    args = parser.parse_args(argv)

    json_path = args.out.with_suffix(".json") if args.out else None
    done: dict[tuple, dict] = {}
    if args.resume and json_path and json_path.exists():
        done = {_key(item): item for item in json.loads(json_path.read_text(encoding="utf-8"))}

    results = []
    for spec in args.cases:
        name, _, seed = spec.partition(":")
        key = (name, int(seed or 0), args.time_limit, args.gamma, args.threads)
        results.append(done.get(key) or compare_case(*key))
        print(f"{'reutilizado' if key in done else 'resuelto'}: {spec}", flush=True)
        if args.out:  # se guarda tras cada caso: una corrida larga interrumpida no se pierde
            args.out.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            report = to_markdown(results, args.time_limit, args.gamma, args.threads)
            args.out.write_text(report + "\n", encoding="utf-8")
    if not args.out:
        print(to_markdown(results, args.time_limit, args.gamma, args.threads))
    return 0 if consistent(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
