# Simulador de Funciones del Kernel de un Sistema Operativo

Proyecto final individual del curso **Sistemas Operativos I** — Universidad Mariano Gálvez de Guatemala.

Simulador de consola (CLI) escrito en Python que modela el comportamiento lógico del núcleo de un
sistema operativo mediante estructuras de datos:

| Componente | Implementación |
|---|---|
| **A. Procesos** | PCB (PID, estado, tamaño, ráfaga total y restante) + TCB por hilo; planificación **Round Robin q = 3** con cambio de contexto simulado |
| **B. Memoria** | RAM física de **100 MB**, asignación contigua dinámica (first-fit), fusión de huecos, compactación y rechazo **Out of Memory** |
| **C. Concurrencia** | Variable global compartida protegida por un **semáforo binario** con `wait()` / `signal()` y cola de espera FIFO |
| **D. Deadlock** | Recurso 1 y Recurso 2, escenario de espera circular forzada, detección por **grafo de espera (DFS)** y resolución abortando una víctima |

## Requisitos

- Python 3.10 o superior. **No** requiere paquetes externos, puertos, bases de datos ni claves de API.

## Ejecución

```bash
python main.py
```

```bash
python main.py --demo
```

```bash
python -m unittest discover -s tests -v
```

Interfaz gráfica opcional para pruebas locales (usa el mismo kernel de Python), en http://127.0.0.1:8765:

```bash
python web/servidor.py
```

`--demo` ejecuta los 4 casos de la bitácora (OOM, Round Robin, semáforo, deadlock); `--demo 4` ejecuta solo uno.

## Estructura

```
main.py                  punto de entrada
simulador/
  config.py              RAM 100 MB, quantum 3, límites de validación
  pcb.py                 PCB, TCB y estados
  memoria.py             administrador de memoria contigua
  planificador.py        Round Robin + cálculo teórico
  concurrencia.py        semáforo binario y sección crítica
  deadlock.py            recursos, grafo de espera y detección
  kernel.py              fachada que coordina los subsistemas
  vistas.py              tablas, mapa de memoria y Gantt
  consola.py             menús y lectura validada de datos
  demo.py                casos de prueba guiados
tests/test_simulador.py  pruebas unitarias
informe/                 generador del informe PDF (datos.json + generar_informe.py)
docs/guion_video.md      guion del video de 5 minutos
```

## Informe

El informe técnico se genera con los datos de `informe/datos.json`:

```bash
python informe/generar_informe.py
```

Requiere Microsoft Edge o Chrome (para imprimir a PDF) y, opcionalmente, `pip install pypdf` para numerar el índice.
