"""
concurrencia.py - Exclusión mutua con Semáforo Binario.

Se modela una "Variable Global Compartida" protegida por una sección
crítica. El acceso se controla con un semáforo binario (valor 0 ó 1) con
operaciones explícitas:

  wait()   (P / down): si valor == 1 -> lo pone en 0 y el proceso entra.
                       si valor == 0 -> el proceso se BLOQUEA y pasa a la
                       cola de espera FIFO del semáforo.
  signal() (V / up):   si hay procesos esperando -> se despierta al primero
                       (pasa directo a la sección crítica, valor sigue en 0).
                       si no hay nadie -> valor = 1.

Se trata de un semáforo con COLA DE ESPERA (sin espera activa / busy
waiting) y con dueño: solo el proceso que hizo wait() puede hacer signal(),
como un mutex. Así se evitan liberaciones accidentales.
"""

from collections import deque
from dataclasses import dataclass, field


class ErrorSincronizacion(Exception):
    """Uso indebido del semáforo (signal sin wait, doble wait, etc.)."""


@dataclass
class SemaforoBinario:
    nombre: str = "mutex_variable_global"
    valor: int = 1
    duenio: int | None = None
    cola_espera: deque = field(default_factory=deque)

    def wait(self, pid: int) -> bool:
        """Devuelve True si el proceso entra; False si queda bloqueado."""
        if self.duenio == pid:
            raise ErrorSincronizacion(f"P{pid} ya está dentro de la sección crítica")
        if pid in self.cola_espera:
            raise ErrorSincronizacion(f"P{pid} ya está esperando en el semáforo")
        if self.valor == 1:
            self.valor = 0
            self.duenio = pid
            return True
        self.cola_espera.append(pid)
        return False

    def signal(self, pid: int) -> int | None:
        """Libera el semáforo. Devuelve el PID despertado (o None)."""
        if self.duenio != pid:
            raise ErrorSincronizacion(
                f"P{pid} no puede hacer signal(): el dueño de la sección crítica es "
                f"{'P' + str(self.duenio) if self.duenio is not None else 'nadie'}")
        if self.cola_espera:
            siguiente = self.cola_espera.popleft()
            self.duenio = siguiente          # entrega directa (valor sigue en 0)
            return siguiente
        self.valor = 1
        self.duenio = None
        return None

    def quitar_de_cola(self, pid: int) -> None:
        if pid in self.cola_espera:
            self.cola_espera.remove(pid)


class SeccionCritica:
    """Región de memoria compartida protegida por el semáforo."""

    def __init__(self):
        self.variable_global = 0
        self.semaforo = SemaforoBinario()
        self.historial: list[tuple[int, int, int]] = []   # (pid, antes, despues)

    def escribir(self, pid: int, delta: int = 1) -> tuple[int, int]:
        """Operación sobre la variable compartida (solo el dueño)."""
        if self.semaforo.duenio != pid:
            raise ErrorSincronizacion(
                f"Violación de exclusión mutua: P{pid} intentó modificar la variable "
                f"global sin estar dentro de la sección crítica")
        antes = self.variable_global
        self.variable_global += delta
        self.historial.append((pid, antes, self.variable_global))
        return antes, self.variable_global


def simular_condicion_carrera(participantes: list[str], incrementos: int,
                              usar_semaforo: bool) -> dict:
    """Demuestra una condición de carrera a nivel de instrucciones.

    Cada participante ejecuta `incrementos` veces la secuencia no atómica:
        LOAD  reg <- compartida
        ADD   reg <- reg + 1
        STORE compartida <- reg
    El "CPU" alterna entre participantes en CADA instrucción (el peor caso
    de intercalado). Sin semáforo se pierden actualizaciones; con semáforo
    (wait antes del LOAD, signal después del STORE) el resultado es exacto.
    """
    compartida = 0
    sem = SemaforoBinario(nombre="mutex_demo")
    traza: list[str] = []
    # Estado por participante: [iteraciones_restantes, paso, registro]
    estado = {p: [incrementos, 0, 0] for p in participantes}
    bloqueados: set[str] = set()
    ids = {p: i for i, p in enumerate(participantes)}
    nombres = {i: p for p, i in ids.items()}
    activos = deque(participantes)

    while activos:
        p = activos.popleft()
        if p in bloqueados:
            activos.append(p)
            continue
        it, paso, reg = estado[p]
        if paso == 0 and usar_semaforo:
            if sem.duenio == ids[p]:
                # signal() de otro proceso ya le entregó la sección crítica.
                traza.append(f"{p}: despierta y entra a la sección crítica")
            elif not sem.wait(ids[p]):
                bloqueados.add(p)
                traza.append(f"{p}: wait() -> BLOQUEADO (sección crítica ocupada)")
                activos.append(p)
                continue
            else:
                traza.append(f"{p}: wait() -> entra a la sección crítica")
        if paso == 0:
            reg = compartida
            traza.append(f"{p}: LOAD  reg={reg}")
        elif paso == 1:
            reg += 1
            traza.append(f"{p}: ADD   reg={reg}")
        else:
            compartida = reg
            traza.append(f"{p}: STORE compartida={compartida}")
            it -= 1
            if usar_semaforo:
                despierto = sem.signal(ids[p])
                if despierto is not None:
                    bloqueados.discard(nombres[despierto])
                    traza.append(f"{p}: signal() -> despierta a {nombres[despierto]}")
                else:
                    traza.append(f"{p}: signal() -> semáforo libre")
        paso = (paso + 1) % 3
        estado[p] = [it, paso, reg]
        if it > 0:
            activos.append(p)

    esperado = len(participantes) * incrementos
    return {"esperado": esperado, "obtenido": compartida,
            "perdidas": esperado - compartida, "traza": traza}
