"""
deadlock.py - Gestor de recursos exclusivos y detección de interbloqueo.

Hay dos recursos de una sola instancia (Recurso 1 y Recurso 2). Cuando un
proceso solicita un recurso ocupado, queda BLOQUEADO en la cola de ese
recurso. La detección se hace construyendo el Grafo de Espera (wait-for
graph): existe una arista Pi -> Pj si Pi espera un recurso que posee Pj.
Un CICLO en ese grafo equivale a un deadlock (con recursos de instancia
única, ciclo <=> interbloqueo).

Estrategia elegida: DETECCIÓN Y RECUPERACIÓN. El sistema permite que el
interbloqueo ocurra, lo detecta y el usuario lo resuelve abortando
(terminando forzosamente) a una víctima, cuyos recursos se liberan y se
entregan al siguiente proceso en espera, rompiendo el ciclo.
"""

from collections import deque
from dataclasses import dataclass, field


class ErrorRecurso(Exception):
    pass


@dataclass
class Recurso:
    rid: int
    nombre: str
    asignado_a: int | None = None
    cola_espera: deque = field(default_factory=deque)


class GestorRecursos:
    def __init__(self, recursos: dict[int, str]):
        self.recursos = {rid: Recurso(rid, nombre) for rid, nombre in recursos.items()}

    def _recurso(self, rid: int) -> Recurso:
        if rid not in self.recursos:
            raise ErrorRecurso(f"No existe el recurso {rid}")
        return self.recursos[rid]

    def solicitar(self, pid: int, rid: int) -> bool:
        """True si se asigna; False si el proceso debe bloquearse."""
        r = self._recurso(rid)
        if r.asignado_a == pid:
            raise ErrorRecurso(f"P{pid} ya posee {r.nombre}")
        if pid in r.cola_espera:
            raise ErrorRecurso(f"P{pid} ya está esperando {r.nombre}")
        if r.asignado_a is None:
            r.asignado_a = pid
            return True
        r.cola_espera.append(pid)
        return False

    def liberar(self, pid: int, rid: int) -> int | None:
        """Libera el recurso; si hay alguien esperando se le asigna.

        Devuelve el PID que recibió el recurso (o None)."""
        r = self._recurso(rid)
        if r.asignado_a != pid:
            raise ErrorRecurso(f"P{pid} no posee {r.nombre}")
        r.asignado_a = r.cola_espera.popleft() if r.cola_espera else None
        return r.asignado_a

    def liberar_todos(self, pid: int) -> list[tuple[int, int]]:
        """Libera todo lo que posee pid y lo saca de todas las colas.

        Devuelve [(rid, pid_despertado), ...]."""
        despertados = []
        for r in self.recursos.values():
            if pid in r.cola_espera:
                r.cola_espera.remove(pid)
        for r in self.recursos.values():
            if r.asignado_a == pid:
                nuevo = self.liberar(pid, r.rid)
                if nuevo is not None:
                    despertados.append((r.rid, nuevo))
        return despertados

    def esperando_algo(self, pid: int) -> bool:
        return any(pid in r.cola_espera for r in self.recursos.values())

    # ---------------------------------------------------------- detección
    def grafo_espera(self) -> dict[int, set[int]]:
        grafo: dict[int, set[int]] = {}
        for r in self.recursos.values():
            if r.asignado_a is None:
                continue
            for esperando in r.cola_espera:
                grafo.setdefault(esperando, set()).add(r.asignado_a)
        return grafo

    def detectar_ciclo(self) -> list[int] | None:
        """DFS con colores sobre el grafo de espera. Devuelve el ciclo o None."""
        grafo = self.grafo_espera()
        BLANCO, GRIS, NEGRO = 0, 1, 2
        color = {n: BLANCO for n in grafo}
        pila: list[int] = []

        def dfs(u: int) -> list[int] | None:
            color[u] = GRIS
            pila.append(u)
            for v in sorted(grafo.get(u, ())):
                if color.get(v, BLANCO) == GRIS:          # arista de retroceso
                    return pila[pila.index(v):] + [v]
                if color.get(v, BLANCO) == BLANCO:
                    ciclo = dfs(v)
                    if ciclo:
                        return ciclo
            pila.pop()
            color[u] = NEGRO
            return None

        for nodo in sorted(grafo):
            if color[nodo] == BLANCO:
                ciclo = dfs(nodo)
                if ciclo:
                    return ciclo
        return None
