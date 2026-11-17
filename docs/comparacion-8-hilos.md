# Comparación de backends

Generado por `timetabling_milp.compare`. Límite de 20 s por resolución, 8 hilo(s) por solver, una ejecución por backend. Datos sintéticos.

- **Objetivo**: reconstruido desde el horario, no el que informa el solver.
- **Cota** y **brecha**: mejor cota inferior del solver y (objetivo − cota) / objetivo.
- **Ventanas**: bloques libres entre clases de un grupo, contados desde la entrada.
- **Voraz** `INCOMPLETE (n/m)`: se atascó tras ubicar n de m secciones; no hay horario.

## medium (semilla 1)

80 secciones, 1697 variables binarias, 1288 restricciones de conflicto.

### Modelo base (relajación lineal: 506.62)

| Backend | Estado | Objetivo | Cota | Brecha | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---|---:|
| voraz | INCOMPLETE (9/80) | — | — | — | — | — | 0.01 |
| cp-sat | OPTIMAL | 734 | 734.0 | 0.0% | 90 | PASSED | 7.74 |
| pyomo+highs | OPTIMAL | 734 | 734.0 | 0.0% | 97 | PASSED | 8.61 |
| pulp+highs | OPTIMAL | 734 | 734.0 | 0.0% | 97 | PASSED | 8.71 |
| pulp+cbc | FEASIBLE | 734 | 576.7 | 21.4% | 90 | PASSED | 20.07 |

### Con compacidad, gamma = 5 (relajación lineal: 682.04)

| Backend | Estado | Objetivo | Cota | Brecha | Costo | Ventanas | Auditoría | Resolución (s) |
|---|---|---:|---:|---:|---:|---:|---|---:|
| cp-sat | FEASIBLE | 1121 | 883.0 | 21.2% | 791 | 66 | PASSED | 20.01 |
| pyomo+highs | FEASIBLE | 1121 | 874.9 | 22.0% | 841 | 56 | PASSED | 20.38 |

