"""
kernel.py - Núcleo del simulador (patrón Fachada).

El Kernel coordina los cuatro subsistemas y es el ÚNICO punto que la
interfaz de consola utiliza:

    Consola (CLI) ──> Kernel ──┬── AdministradorMemoria  (RAM 100 MB)
                               ├── PlanificadorRR        (q = 3)
                               ├── SeccionCritica        (semáforo binario)
                               └── GestorRecursos        (deadlock)

Interacción clave Planificador <-> Memoria:
  * Un proceso solo entra a la cola de listos si el Administrador de
    Memoria le asignó un bloque (si no -> Out of Memory y se rechaza).
  * Cuando el Planificador marca un proceso como TERMINADO, el Kernel
    libera su memoria, sus recursos y el semáforo si lo tenía.
"""

import re
from typing import Callable

from . import config
from .concurrencia import ErrorSincronizacion, SeccionCritica, simular_condicion_carrera
from .deadlock import ErrorRecurso, GestorRecursos
from .memoria import AdministradorMemoria, MemoriaInsuficienteError
from .pcb import PCB, TCB, Estado
from .planificador import PlanificadorRR, TurnoRR

_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-]+$")


class ErrorKernel(Exception):
    """Operación inválida solicitada al kernel (PID inexistente, etc.)."""


class Kernel:
    def __init__(self, ram_mb: int = config.RAM_TOTAL_MB, quantum: int = config.QUANTUM,
                 estrategia: str = config.ESTRATEGIA_MEMORIA,
                 salida: Callable[[str], None] | None = print):
        self.memoria = AdministradorMemoria(ram_mb, estrategia)
        self.planificador = PlanificadorRR(quantum)
        self.seccion_critica = SeccionCritica()
        self.recursos = GestorRecursos(config.RECURSOS)
        self.procesos: dict[int, PCB] = {}
        self.bitacora: list[str] = []
        self.rechazados = 0
        self.pico_ram_mb = 0
        self._siguiente_pid = 1
        self._siguiente_tid = 1
        self._salida = salida

    # ================================================================ utilidades
    @property
    def reloj(self) -> int:
        return self.planificador.reloj

    def _log(self, mensaje: str) -> None:
        linea = f"[t={self.reloj:>3}] {mensaje}"
        self.bitacora.append(linea)
        if self._salida:
            self._salida(linea)

    def obtener(self, pid: int) -> PCB:
        if pid not in self.procesos:
            raise ErrorKernel(f"No existe un proceso con PID {pid}")
        return self.procesos[pid]

    def _vivo(self, pid: int) -> PCB:
        pcb = self.obtener(pid)
        if pcb.estado == Estado.TERMINADO:
            raise ErrorKernel(f"P{pid} ya terminó")
        return pcb

    def _activo(self, pid: int) -> PCB:
        """Proceso vivo y NO bloqueado (un proceso bloqueado no puede ejecutar
        instrucciones como wait() o solicitar recursos)."""
        pcb = self._vivo(pid)
        if pcb.estado == Estado.BLOQUEADO:
            raise ErrorKernel(f"P{pid} está BLOQUEADO ({pcb.motivo_bloqueo}) y no puede ejecutar")
        return pcb

    def vivos(self) -> list[PCB]:
        return [p for p in self.procesos.values() if p.estado != Estado.TERMINADO]

    def _bloquear(self, pcb: PCB, motivo: str) -> None:
        self.planificador.retirar(pcb)
        pcb.cambiar_estado(Estado.BLOQUEADO, motivo)

    def _desbloquear_si_corresponde(self, pcb: PCB) -> None:
        """Regresa a LISTO si ya no espera ningún recurso ni el semáforo."""
        if pcb.estado != Estado.BLOQUEADO:
            return
        if self.recursos.esperando_algo(pcb.pid) or pcb.pid in self.seccion_critica.semaforo.cola_espera:
            return
        self.planificador.admitir(pcb)
        self._log(f"P{pcb.pid} se desbloquea -> LISTO (regresa a la cola de listos)")

    # =========================================================== A. procesos
    def crear_proceso(self, nombre: str, tamano_mb: int, rafaga: int, hilos: int = 1) -> PCB:
        """Crea un proceso. Lanza ValueError (datos inválidos) o
        MemoriaInsuficienteError (OOM)."""
        nombre = (nombre or "").strip()
        if not nombre:
            nombre = f"Proceso{self._siguiente_pid}"
        if len(nombre) > config.NOMBRE_MAX or not _NOMBRE_VALIDO.match(nombre):
            raise ValueError(f"Nombre inválido: use letras, números, '_' o '-' "
                             f"(máximo {config.NOMBRE_MAX} caracteres)")
        for valor, etiqueta, minimo, maximo in (
                (tamano_mb, "Tamaño", config.TAMANO_MIN_MB, config.TAMANO_MAX_MB),
                (rafaga, "Ráfaga", config.RAFAGA_MIN, config.RAFAGA_MAX),
                (hilos, "Hilos", config.HILOS_MIN, config.HILOS_MAX)):
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise ValueError(f"{etiqueta} debe ser un número entero")
            if not minimo <= valor <= maximo:
                raise ValueError(f"{etiqueta} fuera de rango [{minimo}..{maximo}]: {valor}")

        pid = self._siguiente_pid
        # 1) Validar memoria ANTES de crear el PCB (admisión).
        try:
            base = self.memoria.asignar(pid, tamano_mb)
        except MemoriaInsuficienteError as e:
            self.rechazados += 1
            self._log(f"RECHAZADO '{nombre}' ({tamano_mb} MB): {e}")
            raise
        self._siguiente_pid += 1
        self.pico_ram_mb = max(self.pico_ram_mb, self.memoria.usada)

        # 2) Crear PCB + TCB(s) y admitir en la cola de listos.
        pcb = PCB(pid=pid, nombre=nombre, tamano_mb=tamano_mb, rafaga_total=rafaga,
                  rafaga_restante=rafaga, direccion_base=base, tiempo_llegada=self.reloj)
        for _ in range(hilos):
            pcb.hilos.append(TCB(tid=self._siguiente_tid, pid=pid))
            self._siguiente_tid += 1
        self.procesos[pid] = pcb
        self.planificador.admitir(pcb)
        self._log(f"CREADO P{pid} '{nombre}' | {tamano_mb} MB en [{base}-{base + tamano_mb}) "
                  f"| ráfaga={rafaga} | hilos={hilos} | RAM libre={self.memoria.libre} MB")
        return pcb

    def ejecutar_turno(self) -> TurnoRR | None:
        turno = self.planificador.ejecutar_turno()
        if turno is None:
            bloqueados = [p for p in self.vivos() if p.estado == Estado.BLOQUEADO]
            if bloqueados:
                self._log("Cola de listos vacía; procesos BLOQUEADOS: "
                          + ", ".join(f"P{p.pid}({p.motivo_bloqueo})" for p in bloqueados))
            else:
                self._log("Cola de listos vacía: CPU ociosa")
            return None
        pcb = self.procesos[turno.pid]
        if turno.termino:
            self._log(f"CPU -> P{turno.pid} [{turno.inicio}-{turno.fin}] ráfaga restante=0 "
                      f"=> TERMINADO")
            self._liberar_todo(pcb)
        else:
            self._log(f"CPU -> P{turno.pid} [{turno.inicio}-{turno.fin}] quantum agotado, "
                      f"restante={turno.restante} => CAMBIO DE CONTEXTO (TCB T{turno.tid} guardado), "
                      f"vuelve al final de la cola")
        return turno

    def ejecutar_todo(self, max_turnos: int = 100_000) -> list[TurnoRR]:
        turnos = []
        while self.planificador.hay_listos() and len(turnos) < max_turnos:
            turnos.append(self.ejecutar_turno())
        if not self.planificador.hay_listos():
            self.ejecutar_turno()   # reporta CPU ociosa / bloqueados
        return turnos

    def abortar(self, pid: int, motivo: str = "abortado por el usuario") -> None:
        """Terminación forzosa (kill): libera memoria, recursos y semáforo."""
        pcb = self._vivo(pid)
        self.planificador.retirar(pcb)
        pcb.cambiar_estado(Estado.TERMINADO)
        pcb.abortado = True
        pcb.tiempo_fin = self.reloj
        self._log(f"ABORTADO P{pid} '{pcb.nombre}' ({motivo})")
        self._liberar_todo(pcb)

    def _liberar_todo(self, pcb: PCB) -> None:
        liberado = self.memoria.liberar(pcb.pid)
        self._log(f"  memoria liberada: {liberado} MB de P{pcb.pid} | RAM libre={self.memoria.libre} MB")

        sem = self.seccion_critica.semaforo
        sem.quitar_de_cola(pcb.pid)
        if sem.duenio == pcb.pid:
            despierto = sem.signal(pcb.pid)
            self._log(f"  P{pcb.pid} tenía la sección crítica: signal() automático")
            if despierto is not None:
                self._log(f"  P{despierto} entra a la sección crítica")
                self._desbloquear_si_corresponde(self.procesos[despierto])

        for rid, nuevo in self.recursos.liberar_todos(pcb.pid):
            self._log(f"  {config.RECURSOS[rid]} liberado por P{pcb.pid} y asignado a P{nuevo}")
            self.procesos[nuevo].recursos.add(rid)
            self._desbloquear_si_corresponde(self.procesos[nuevo])
        pcb.recursos.clear()

    # ====================================================== B. memoria extra
    def compactar_memoria(self) -> None:
        nuevas = self.memoria.compactar()
        for pid, base in nuevas.items():
            self.procesos[pid].direccion_base = base
        self._log(f"COMPACTACIÓN: huecos unidos, mayor hueco = {self.memoria.mayor_hueco} MB")

    # ======================================================= C. concurrencia
    def sc_wait(self, pid: int) -> bool:
        pcb = self._activo(pid)
        try:
            entro = self.seccion_critica.semaforo.wait(pid)
        except ErrorSincronizacion as e:
            raise ErrorKernel(str(e)) from e
        if entro:
            self._log(f"wait() P{pid}: semáforo 1->0, entra a la SECCIÓN CRÍTICA")
        else:
            self._bloquear(pcb, "espera semáforo")
            cola = ", ".join(f"P{x}" for x in self.seccion_critica.semaforo.cola_espera)
            self._log(f"wait() P{pid}: sección crítica OCUPADA por "
                      f"P{self.seccion_critica.semaforo.duenio} -> BLOQUEADO. Cola semáforo: [{cola}]")
        return entro

    def sc_escribir(self, pid: int, delta: int = 1) -> int:
        self._vivo(pid)
        try:
            antes, despues = self.seccion_critica.escribir(pid, delta)
        except ErrorSincronizacion as e:
            self._log(f"DENEGADO: {e}")
            raise ErrorKernel(str(e)) from e
        self._log(f"P{pid} modifica la variable global: {antes} -> {despues}")
        return despues

    def sc_signal(self, pid: int) -> int | None:
        self._vivo(pid)
        try:
            despierto = self.seccion_critica.semaforo.signal(pid)
        except ErrorSincronizacion as e:
            raise ErrorKernel(str(e)) from e
        if despierto is None:
            self._log(f"signal() P{pid}: sale de la sección crítica, semáforo 0->1")
        else:
            self._log(f"signal() P{pid}: sale; despierta a P{despierto}, que entra a la sección crítica")
            self._desbloquear_si_corresponde(self.procesos[despierto])
        return despierto

    def demo_condicion_carrera(self, incrementos: int = 3) -> tuple[dict, dict]:
        vivos = [f"P{p.pid}" for p in self.vivos()][:3]
        participantes = vivos if len(vivos) >= 2 else ["H1", "H2", "H3"]
        sin = simular_condicion_carrera(participantes, incrementos, usar_semaforo=False)
        con = simular_condicion_carrera(participantes, incrementos, usar_semaforo=True)
        self._log(f"CONDICIÓN DE CARRERA {participantes} x{incrementos}: sin semáforo="
                  f"{sin['obtenido']}/{sin['esperado']}, con semáforo={con['obtenido']}/{con['esperado']}")
        return sin, con

    # ========================================================== D. deadlock
    def solicitar_recurso(self, pid: int, rid: int) -> bool:
        pcb = self._activo(pid)
        try:
            asignado = self.recursos.solicitar(pid, rid)
        except ErrorRecurso as e:
            raise ErrorKernel(str(e)) from e
        nombre = config.RECURSOS[rid]
        if asignado:
            pcb.recursos.add(rid)
            self._log(f"P{pid} obtiene {nombre}")
        else:
            duenio = self.recursos.recursos[rid].asignado_a
            self._bloquear(pcb, f"espera {nombre}")
            self._log(f"P{pid} solicita {nombre} (retenido por P{duenio}) -> BLOQUEADO")
            self.detectar_deadlock(silencioso=True)
        return asignado

    def liberar_recurso(self, pid: int, rid: int) -> None:
        pcb = self._vivo(pid)
        try:
            nuevo = self.recursos.liberar(pid, rid)
        except ErrorRecurso as e:
            raise ErrorKernel(str(e)) from e
        pcb.recursos.discard(rid)
        self._log(f"P{pid} libera {config.RECURSOS[rid]}")
        if nuevo is not None:
            self.procesos[nuevo].recursos.add(rid)
            self._log(f"  {config.RECURSOS[rid]} asignado a P{nuevo}")
            self._desbloquear_si_corresponde(self.procesos[nuevo])

    def detectar_deadlock(self, silencioso: bool = False) -> list[int] | None:
        ciclo = self.recursos.detectar_ciclo()
        if ciclo:
            camino = " -> ".join(f"P{p}" for p in ciclo)
            self._log(f"*** ALERTA: DEADLOCK DETECTADO *** espera circular: {camino}")
            self._log(f"    Use 'Abortar proceso' sobre alguno de: "
                      + ", ".join(f"P{p}" for p in ciclo[:-1]))
        elif not silencioso:
            self._log("Detección: no existe interbloqueo (grafo de espera sin ciclos)")
        return ciclo

    def forzar_deadlock(self) -> list[int] | None:
        """Escenario del enunciado: A retiene R1 y pide R2; B retiene R2 y pide R1."""
        for r in self.recursos.recursos.values():
            if r.asignado_a is not None or r.cola_espera:
                raise ErrorKernel(f"{r.nombre} está en uso; libérelo o reinicie antes de forzar el deadlock")
        self._log("=== Forzando escenario de espera circular (Proceso A / Proceso B) ===")
        a = self.crear_proceso("Proceso_A", 10, 6)
        b = self.crear_proceso("Proceso_B", 10, 6)
        self.solicitar_recurso(a.pid, 1)
        self.solicitar_recurso(b.pid, 2)
        self.solicitar_recurso(a.pid, 2)
        self.solicitar_recurso(b.pid, 1)
        return self.recursos.detectar_ciclo()

    # ======================================================= estadísticas
    def estadisticas(self) -> dict:
        terminados = [p for p in self.procesos.values()
                      if p.estado == Estado.TERMINADO and not p.abortado]
        n = len(terminados) or 1
        tiempo_cpu = sum(t.fin - t.inicio for t in self.planificador.gantt)
        return {
            # Utilización de CPU = tiempo ocupado / tiempo total.
            "utilizacion_cpu": tiempo_cpu / self.reloj * 100 if self.reloj else 0.0,
            # Rendimiento (throughput) = procesos terminados por unidad de tiempo.
            "rendimiento": len(terminados) / self.reloj if self.reloj else 0.0,
            "utilizacion_ram": self.memoria.usada / self.memoria.total * 100,
            "pico_ram": self.pico_ram_mb / self.memoria.total * 100,
            "reloj": self.reloj,
            "creados": len(self.procesos),
            "rechazados_oom": self.rechazados,
            "terminados": len(terminados),
            "abortados": sum(1 for p in self.procesos.values() if p.abortado),
            "cambios_contexto": self.planificador.total_cambios_contexto,
            "espera_promedio": sum(p.tiempo_espera for p in terminados) / n,
            "retorno_promedio": sum(p.tiempo_retorno for p in terminados) / n,
            "respuesta_promedio": sum(p.tiempo_respuesta for p in terminados) / n,
        }
