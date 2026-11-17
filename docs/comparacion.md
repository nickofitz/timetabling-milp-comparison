# Comparación de backends

Generado por `timetabling_milp.compare`. Límite de 20 s por resolución, 1 hilo(s) por solver, una ejecución por backend. Datos sintéticos.

- **Objetivo**: reconstruido desde el horario, no el que informa el solver.
- **Cota** y **brecha**: mejor cota inferior del solver y (objetivo − cota) / objetivo.
- **Ventanas**: bloques libres entre clases de un grupo, contados desde la entrada.
- **Voraz** `INCOMPLETE (n/m)`: se atascó tras ubicar n de m secciones; no hay horario.

## micro (semilla 0)

3 secciones, 5 variables binarias, 4 restricciones de conflicto.

### Modelo base (relajación lineal: 3.00)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | COMPLETE (3/3) | 3 | — | — | 0 | PASSED | 0.00 |
| cp-sat | OPTIMAL | 3 | 3.0 | 0.0% | 0 | PASSED | 0.01 |
| pyomo+highs | OPTIMAL | 3 | 3.0 | 0.0% | 0 | PASSED | 0.01 |
| pulp+highs | OPTIMAL | 3 | 3.0 | 0.0% | 0 | PASSED | 0.00 |
| pulp+cbc | OPTIMAL | 3 | — | — | 0 | PASSED | 0.02 |

### Con compacidad, gamma = 5 (relajación lineal: 3.00)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | OPTIMAL | 3 | 3.0 | 0.0% | 3 | 0 | PASSED | 0.00 |
| pyomo+highs | OPTIMAL | 3 | 3.0 | 0.0% | 3 | 0 | PASSED | 0.01 |

## demo (semilla 42)

12 secciones, 125 variables binarias, 836 restricciones de conflicto.

### Modelo base (relajación lineal: 17.00)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | COMPLETE (12/12) | 21 | — | — | 80 | PASSED | 0.00 |
| cp-sat | OPTIMAL | 17 | 17.0 | 0.0% | 34 | PASSED | 0.00 |
| pyomo+highs | OPTIMAL | 17 | 17.0 | 0.0% | 56 | PASSED | 0.02 |
| pulp+highs | OPTIMAL | 17 | 17.0 | 0.0% | 56 | PASSED | 0.01 |
| pulp+cbc | OPTIMAL | 17 | 17.0 | 0.0% | 8 | PASSED | 0.04 |

### Con compacidad, gamma = 5 (relajación lineal: 17.00)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | OPTIMAL | 17 | 17.0 | 0.0% | 17 | 0 | PASSED | 0.04 |
| pyomo+highs | OPTIMAL | 17 | 17.0 | 0.0% | 17 | 0 | PASSED | 0.11 |

## small (semilla 1)

30 secciones, 318 variables binarias, 528 restricciones de conflicto.

### Modelo base (relajación lineal: 204.86)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | INCOMPLETE (2/30) | — | — | — | — | — | 0.00 |
| cp-sat | OPTIMAL | 242 | 242.0 | 0.0% | 44 | PASSED | 0.12 |
| pyomo+highs | OPTIMAL | 242 | 242.0 | 0.0% | 32 | PASSED | 1.07 |
| pulp+highs | OPTIMAL | 242 | 242.0 | 0.0% | 32 | PASSED | 1.06 |
| pulp+cbc | OPTIMAL | 242 | 242.0 | 0.0% | 32 | PASSED | 0.40 |

### Con compacidad, gamma = 5 (relajación lineal: 299.89)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | OPTIMAL | 387 | 387.0 | 0.0% | 252 | 27 | PASSED | 2.69 |
| pyomo+highs | OPTIMAL | 387 | 387.0 | 0.0% | 252 | 27 | PASSED | 7.19 |

## medium (semilla 1)

80 secciones, 1697 variables binarias, 1288 restricciones de conflicto.

### Modelo base (relajación lineal: 506.62)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | INCOMPLETE (9/80) | — | — | — | — | — | 0.01 |
| cp-sat | FEASIBLE | 786 | 303.0 | 61.5% | 80 | PASSED | 20.00 |
| pyomo+highs | OPTIMAL | 734 | 734.0 | 0.0% | 97 | PASSED | 6.89 |
| pulp+highs | OPTIMAL | 734 | 734.0 | 0.0% | 97 | PASSED | 6.87 |
| pulp+cbc | FEASIBLE | 734 | 576.7 | 21.4% | 94 | PASSED | 20.06 |

### Con compacidad, gamma = 5 (relajación lineal: 682.04)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | FEASIBLE | 1301 | 306.0 | 76.5% | 931 | 74 | PASSED | 20.00 |
| pyomo+highs | FEASIBLE | 1171 | 855.9 | 26.9% | 861 | 62 | PASSED | 20.12 |

## large (semilla 1)

200 secciones, 9236 variables binarias, 3467 restricciones de conflicto.

### Modelo base (relajación lineal: 725.74)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | INCOMPLETE (46/200) | — | — | — | — | — | 0.13 |
| cp-sat | FEASIBLE | 2798 | 300.0 | 89.3% | 214 | PASSED | 20.01 |
| pyomo+highs | FEASIBLE | 788 | 776.0 | 1.5% | 243 | PASSED | 20.16 |
| pulp+highs | FEASIBLE | 788 | 776.0 | 1.5% | 243 | PASSED | 20.06 |
| pulp+cbc | FEASIBLE | 806 | 757.6 | 6.0% | 251 | PASSED | 20.31 |

### Con compacidad, gamma = 5 (relajación lineal: 1278.94)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | FEASIBLE | 4596 | 300.0 | 93.5% | 3431 | 233 | PASSED | 20.00 |
| pyomo+highs | FEASIBLE | 1992 | 1397.7 | 29.8% | 1007 | 197 | PASSED | 20.89 |

