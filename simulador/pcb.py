"""
pcb.py - Estructuras de control: PCB (Process Control Block) y TCB (Thread
Control Block).

El PCB es la "ficha" que el kernel mantiene por cada proceso. El enunciado
exige como mínimo: PID, Estado actual, Tamaño en memoria, Ráfaga de CPU
total y Ráfaga de CPU restante. Además se agregan campos de contabilidad
(tiempos, cambios de contexto) y la lista de hilos (TCB) del proceso.
"""

from dataclasses import dataclass, field
from enum import Enum


class Estado(str, Enum):
    """Estados del modelo clásico de 5 estados de un proceso."""
    NUEVO = "NUEVO"
    LISTO = "LISTO"
    EJECUCION = "EJECUCION"
    BLOQUEADO = "BLOQUEADO"
    TERMINADO = "TERMINADO"


@dataclass
class TCB:
    """Thread Control Block: contexto propio de cada hilo de un proceso.

    Los hilos comparten el espacio de memoria del proceso (por eso el TCB no
    guarda tamaño de memoria), pero cada uno tiene su propio contador de
    programa y su propio juego de registros, que se guardan en cada cambio
    de contexto.
    """
    tid: int
    pid: int
    estado: Estado = Estado.NUEVO
    contador_programa: int = 0
    registros: dict = field(default_factory=lambda: {"AX": 0, "BX": 0, "CX": 0, "DX": 0})


@dataclass
class PCB:
    """Process Control Block."""
    pid: int
    nombre: str
    tamano_mb: int
    rafaga_total: int
    rafaga_restante: int
    estado: Estado = Estado.NUEVO
    direccion_base: int | None = None      # inicio del bloque en RAM (MB)
    tiempo_llegada: int = 0                # reloj del sistema al crearse
    tiempo_primera_cpu: int | None = None  # para el tiempo de respuesta
    tiempo_fin: int | None = None
    cambios_contexto: int = 0
    motivo_bloqueo: str | None = None
    abortado: bool = False                 # terminado forzosamente (kill)
    hilos: list[TCB] = field(default_factory=list)
    recursos: set[int] = field(default_factory=set)
    _turno_hilo: int = 0                   # índice del hilo que toca ejecutar

    # ----------------------------------------------------------------- hilos
    def hilo_activo(self) -> TCB:
        """Hilo que recibe la CPU en este turno (RR interno entre hilos)."""
        return self.hilos[self._turno_hilo % len(self.hilos)]

    def guardar_contexto(self, unidades_ejecutadas: int) -> TCB:
        """Simula el guardado del contexto del hilo que estaba en CPU.

        Avanza su contador de programa y vuelca valores en los registros
        para que el cambio de contexto sea visible en la tabla de TCB.
        """
        hilo = self.hilo_activo()
        hilo.contador_programa += unidades_ejecutadas
        hilo.registros["AX"] = self.rafaga_restante
        hilo.registros["BX"] = self.rafaga_total - self.rafaga_restante
        hilo.registros["CX"] += 1
        hilo.registros["DX"] = self.direccion_base or 0
        hilo.estado = Estado.LISTO
        self._turno_hilo += 1
        return hilo

    def cambiar_estado(self, nuevo: Estado, motivo: str | None = None) -> None:
        """Cambia el estado del proceso y lo propaga a todos sus hilos."""
        self.estado = nuevo
        self.motivo_bloqueo = motivo if nuevo == Estado.BLOQUEADO else None
        for hilo in self.hilos:
            hilo.estado = nuevo

    # ------------------------------------------------------------- métricas
    @property
    def tiempo_retorno(self) -> int | None:
        """Turnaround = fin - llegada (no aplica a procesos abortados)."""
        if self.tiempo_fin is None or self.abortado:
            return None
        return self.tiempo_fin - self.tiempo_llegada

    @property
    def tiempo_espera(self) -> int | None:
        """Espera = retorno - ráfaga total (tiempo en cola de listos)."""
        if self.tiempo_retorno is None:
            return None
        return self.tiempo_retorno - self.rafaga_total

    @property
    def tiempo_respuesta(self) -> int | None:
        if self.tiempo_primera_cpu is None:
            return None
        return self.tiempo_primera_cpu - self.tiempo_llegada
