"""
planificador.py - Planificador de CPU con algoritmo Round Robin (q = 3).

Funcionamiento:
  1. Los procesos admitidos (con memoria asignada) entran al FINAL de la
     cola de listos (FIFO).
  2. El despachador toma el proceso del FRENTE de la cola y le entrega la
     CPU durante min(quantum, ráfaga_restante) unidades de tiempo.
  3. Si el proceso termina dentro del quantum -> estado TERMINADO.
  4. Si se agota el quantum y aún le queda ráfaga -> se produce un cambio
     de contexto simulado (se guarda el TCB del hilo) y el proceso vuelve
     al FINAL de la cola de listos.

El planificador solo conoce la cola de listos; la liberación de memoria y
de recursos al terminar la hace el Kernel (fachada) mediante un callback.
"""

from collections import deque
from dataclasses import dataclass

from .pcb import PCB, Estado


@dataclass
class TurnoRR:
    """Resultado de un turno de CPU (para la bitácora y el diagrama de Gantt)."""
    pid: int
    nombre: str
    inicio: int
    fin: int
    restante: int
    termino: bool
    cambio_contexto: bool
    tid: int


class PlanificadorRR:
    def __init__(self, quantum: int = 3):
        if quantum <= 0:
            raise ValueError("El quantum debe ser positivo")
        self.quantum = quantum
        self.cola_listos: deque[PCB] = deque()
        self.reloj = 0
        self.gantt: list[TurnoRR] = []
        self.total_cambios_contexto = 0

    # ------------------------------------------------------ manejo de cola
    def admitir(self, pcb: PCB) -> None:
        """NUEVO/BLOQUEADO -> LISTO: el proceso se encola al final."""
        pcb.cambiar_estado(Estado.LISTO)
        if pcb not in self.cola_listos:
            self.cola_listos.append(pcb)

    def retirar(self, pcb: PCB) -> None:
        """Saca un proceso de la cola (bloqueo o aborto)."""
        if pcb in self.cola_listos:
            self.cola_listos.remove(pcb)

    def hay_listos(self) -> bool:
        return bool(self.cola_listos)

    # ------------------------------------------------------------ despacho
    def ejecutar_turno(self) -> TurnoRR | None:
        """Ejecuta un único quantum. Devuelve None si la cola está vacía."""
        if not self.cola_listos:
            return None

        pcb = self.cola_listos.popleft()
        pcb.cambiar_estado(Estado.EJECUCION)
        if pcb.tiempo_primera_cpu is None:
            pcb.tiempo_primera_cpu = self.reloj

        tid = pcb.hilo_activo().tid
        unidades = min(self.quantum, pcb.rafaga_restante)
        inicio = self.reloj
        self.reloj += unidades
        pcb.rafaga_restante -= unidades

        termino = pcb.rafaga_restante == 0
        cambio = False
        if termino:
            pcb.cambiar_estado(Estado.TERMINADO)
            pcb.tiempo_fin = self.reloj
        else:
            # Quantum agotado: cambio de contexto y regreso al final de la cola.
            pcb.guardar_contexto(unidades)
            pcb.cambios_contexto += 1
            self.total_cambios_contexto += 1
            cambio = True
            pcb.cambiar_estado(Estado.LISTO)
            self.cola_listos.append(pcb)

        turno = TurnoRR(pcb.pid, pcb.nombre, inicio, self.reloj,
                        pcb.rafaga_restante, termino, cambio, tid)
        self.gantt.append(turno)
        return turno

    # --------------------------------------------------------- diagramas
    def diagrama_gantt(self, ultimos: int | None = None) -> str:
        """Gantt en texto: | P1 | P2 | ... con las marcas de tiempo debajo."""
        turnos = self.gantt[-ultimos:] if ultimos else self.gantt
        if not turnos:
            return "(sin ejecuciones todavía)"
        celdas, tiempos = "|", str(turnos[0].inicio)
        for t in turnos:
            etiqueta = f" P{t.pid} "
            ancho = max(len(etiqueta), len(str(t.fin)) + 1)
            celdas += etiqueta.center(ancho) + "|"
            # El número de fin queda alineado bajo la barra "|" de cierre.
            tiempos = tiempos.ljust(len(celdas) - len(str(t.fin))) + str(t.fin)
        return celdas + "\n" + tiempos


def simular_rr_teorico(rafagas: list[tuple[str, int]], quantum: int = 3) -> dict:
    """Cálculo teórico de RR para procesos que llegan en t = 0.

    Es una función pura (no toca el kernel) que sirve para el análisis
    teórico del informe y para verificar en las pruebas que la simulación
    produce exactamente los mismos tiempos.
    """
    cola = deque((n, r) for n, r in rafagas)
    restante = dict(rafagas)
    reloj, secuencia, fin, primera = 0, [], {}, {}
    while cola:
        nombre, _ = cola.popleft()
        primera.setdefault(nombre, reloj)
        u = min(quantum, restante[nombre])
        secuencia.append((nombre, reloj, reloj + u))
        reloj += u
        restante[nombre] -= u
        if restante[nombre] == 0:
            fin[nombre] = reloj
        else:
            cola.append((nombre, restante[nombre]))
    filas = []
    for nombre, rafaga in rafagas:
        filas.append({
            "nombre": nombre, "rafaga": rafaga, "fin": fin[nombre],
            "retorno": fin[nombre], "espera": fin[nombre] - rafaga,
            "respuesta": primera[nombre],
        })
    n = len(filas) or 1
    return {
        "secuencia": secuencia,
        "filas": filas,
        "espera_promedio": sum(f["espera"] for f in filas) / n,
        "retorno_promedio": sum(f["retorno"] for f in filas) / n,
        "respuesta_promedio": sum(f["respuesta"] for f in filas) / n,
        "cambios_contexto": sum(1 for _ in secuencia) - len(filas),
    }
