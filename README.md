# Timetabling MILP: la misma formulación en Pyomo y PuLP

Versión alternativa del MVP de programación académica
[academic-timetabling-demo](https://github.com/nickofitz/academic-timetabling-demo).
Aquel resuelve el problema con OR-Tools CP-SAT; este lo resuelve como programa lineal
entero (MILP) con dos modeladores, Pyomo y PuLP, y compara los tres sobre las mismas
instancias sintéticas. Añade además lo que al original le falta para que la comparación
diga algo: instancias grandes y una restricción blanda que acopla secciones.

No reimplementa nada del original: lo incluye como submódulo de git fijado a un commit
(`vendor/academic-timetabling-demo`) y lo usa como dependencia de solo lectura: datos,
prefiltro SQL, modelo CP-SAT de referencia, heurística voraz y auditor independiente.

## El modelo

Tras el prefiltro SQL del MVP, cada sección `s` tiene un conjunto `A_s` de alternativas
admisibles (patrón horario, sala). El problema es un set partitioning con conflictos:

```
min  sum_a c_a x_a                    c_a = alpha * D_a + beta * E_a
s.a. sum_{a in A_s} x_a  = 1          cada sección elige una alternativa
     sum_{a in K_q} x_a <= 1          cada ocupación (recurso, semana, día, bloque) se usa a lo más una vez
     x_a en {0, 1}
```

Es idéntico al modelo CP-SAT del original. Lo que cambia es el paradigma de resolución
(branch and cut sobre la relajación lineal, en vez de propagación con aprendizaje de
cláusulas) y la forma de escribirlo.

## La misma restricción, tres veces

```python
# OR-Tools CP-SAT (original): restricciones lógicas nativas
model.add_exactly_one(x[a] for a in by_section[s])


# Pyomo: conjuntos y restricciones indexadas, como en la notación algebraica
@model.Constraint(model.S)
def assignment(m, s):
    return sum(m.x[a] for a in data.by_section[s]) == 1


# PuLP: se suman expresiones a un problema; los índices son estructuras de Python
problem += pulp.lpSum(x[a] for a in alternatives) == 1, f"assignment_{index}"
```

| | CP-SAT | Pyomo | PuLP |
|---|---|---|---|
| Qué es | Solver con API propia | Lenguaje de modelado | Lenguaje de modelado |
| Solver | El propio | Intercambiable (aquí HiGHS) | Intercambiable (aquí HiGHS y CBC) |
| Modelo separado de los datos | No | Sí (`Set`, `Param`) | No |
| Transformar el modelo (p. ej. relajarlo) | No | Sí, sin reescribirlo | Reconstruyéndolo |
| Variables continuas | No | Sí | Sí |
| Restricciones lógicas nativas | Sí | Vía GDP | No |

## Uso

Requiere [uv](https://docs.astral.sh/uv/). El original viene como submódulo:

```
git clone --recurse-submodules <URL de este repositorio>
uv sync
uv run pytest
uv run python -m timetabling_milp.compare --out docs/comparacion.md
uv run python -m timetabling_milp.compare --threads 8 --cases medium:1 large:1 --out docs/comparacion-8-hilos.md
```

`--resume` reutiliza los casos ya resueltos del `.json` vecino; `--time-limit` y `--gamma`
cambian el límite por resolución y el costo de cada ventana.

## Instancias

| Caso | Origen | Secciones | Variables | Ocupación de salas |
|---|---|---:|---:|---:|
| `micro`, `demo` | Generador del original | 3 y 12 | 5 y 125 | baja |
| `small` | `generator.py` | 30 | 318 | ≈ 70 % |
| `medium` | `generator.py` | 80 | 1 697 | ≈ 80 % |
| `large` | `generator.py` | 200 | 9 236 | ≈ 82 % |

`generator.py` planta primero un horario sin choques y deriva de él matrícula, patrones
autorizados e indisponibilidades, de modo que toda instancia es factible por construcción.

## Compacidad

Una ventana es un bloque libre entre dos clases de un mismo grupo en un mismo día. El modelo
extendido minimiza `costo + gamma * ventanas`. A diferencia del modelo base, este objetivo
depende de lo que eligen varias secciones a la vez. La formulación (sin big-M) está
documentada en `compactness.py` y se implementa en Pyomo y en CP-SAT. No se implementó en
PuLP: sería una tercera copia casi idéntica y no cambiaría ninguna conclusión.

## Resultados

Informes completos en `docs/comparacion.md` (1 hilo) y `docs/comparacion-8-hilos.md`.
Límite de 20 s por resolución. Objetivo y, entre paréntesis, brecha respecto de la cota.

| Instancia y modelo | CP-SAT, 1 hilo | CP-SAT, 8 hilos | Pyomo + HiGHS, 1 hilo |
|---|---:|---:|---:|
| `small`, base | 242 (óptimo) | — | 242 (óptimo) |
| `small`, compacidad | 387 (óptimo) | — | 387 (óptimo) |
| `medium`, base | 786 (61,5 %) | 734 (óptimo) | 734 (óptimo) |
| `medium`, compacidad | 1 301 (76,5 %) | 1 121 (21,2 %) | 1 171 (26,9 %) |
| `large`, base | 2 798 (89,3 %) | — | 788 (1,5 %) |
| `large`, compacidad | 4 596 (93,5 %) | — | 1 992 (29,8 %) |

Qué se puede afirmar:

- **Todos los horarios pasan el auditor** y, cuando dos backends demuestran optimalidad,
  coinciden en el valor.
- **La heurística voraz del original no completa ninguna instancia ajustada** (ubica 2 de
  30, 9 de 80 y 46 de 200 secciones). Sin retroceso, una ocupación alta la bloquea.
- **CP-SAT depende del número de workers.** Con uno, que es el valor por defecto de la
  configuración del original, no cierra `medium`; con ocho la resuelve en un tiempo
  similar al de HiGHS. Compararlo con un solo worker lo subestima.
- **HiGHS da cotas mucho mejores en el modelo base**, porque la relajación lineal de un
  set partitioning con cliques es fuerte (en `large`, relajación 725,7 frente a un mejor
  valor de 788).
- **La compacidad vuelve difícil el problema para ambos**: ninguno cierra `medium` en 20 s.
- **El modelo base tiene muchos óptimos equivalentes en costo y muy distintos en
  ventanas**: en `demo` los backends devuelven horarios óptimos con 8, 34 o 56 ventanas, y
  el modelo con compacidad encuentra uno con 0 al mismo costo.

## Límites

- Una sola semilla por tamaño y una sola ejecución por backend: son observaciones, no un
  benchmark. Para afirmar que un solver es mejor harían falta varias semillas y tiempos
  más largos.
- `large` con 8 hilos no está en el informe: los resultados se generaron en una máquina de
  2 núcleos con un tope de 3 minutos por comando, y ese caso lo excede. El segundo comando
  de la sección Uso lo genera.
- Los datos son sintéticos y el generador fija su propia mezcla de secciones y patrones.
- HiGHS resuelve el árbol de búsqueda esencialmente en serie: darle más hilos casi no cambia
  su resultado.

## Estructura

```
src/timetabling_milp/
  instance.py     datos del modelo, leídos de las tablas del MVP original
  generator.py    instancias sintéticas de tamaño configurable, con solución plantada
  compactness.py  ventanas: datos, conteo desde el modelo y conteo independiente
  pyomo_model.py  formulación en Pyomo, compacidad como bloque, relajación lineal
  pulp_model.py   formulación base en PuLP, HiGHS o CBC
  cpsat_model.py  CP-SAT con compacidad opcional
  compare.py      ejecuta todos los backends y genera los informes
tests/
vendor/academic-timetabling-demo/   submódulo: el MVP original, sin modificar
```

Para actualizar el original a un commit más reciente: `git -C vendor/academic-timetabling-demo
checkout <commit>`, ejecutar las pruebas y confirmar el cambio del submódulo.
