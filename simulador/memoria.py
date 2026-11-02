"""
memoria.py - Administrador de Memoria.

Modelo: Asignación Contigua Dinámica (particiones variables) sobre una RAM
física de 100 MB. La memoria se representa como una lista ordenada de
bloques; cada bloque está libre (hueco) o pertenece a un PID.

  * Al crear un proceso se busca un hueco con la estrategia configurada
    (first-fit por defecto). Si ningún hueco alcanza, se lanza
    MemoriaInsuficienteError ("Out of Memory") y el proceso se rechaza.
  * Al terminar/abortar un proceso su bloque se libera y se fusiona con
    los huecos vecinos (coalescencia) para reducir la fragmentación.
  * Opcionalmente se puede compactar la memoria para juntar todos los
    huecos al final (solución a la fragmentación externa).
"""

from dataclasses import dataclass


class MemoriaInsuficienteError(Exception):
    """Error de desbordamiento: no hay espacio contiguo para el proceso."""


@dataclass
class Bloque:
    inicio: int          # dirección base en MB
    tamano: int          # tamaño en MB
    pid: int | None = None   # None => hueco libre

    @property
    def libre(self) -> bool:
        return self.pid is None

    @property
    def fin(self) -> int:
        return self.inicio + self.tamano


class AdministradorMemoria:
    ESTRATEGIAS = ("first-fit", "best-fit", "worst-fit")

    def __init__(self, total_mb: int = 100, estrategia: str = "first-fit"):
        if estrategia not in self.ESTRATEGIAS:
            raise ValueError(f"Estrategia desconocida: {estrategia}")
        self.total = total_mb
        self.estrategia = estrategia
        self.bloques: list[Bloque] = [Bloque(0, total_mb)]

    # ------------------------------------------------------------ consultas
    @property
    def libre(self) -> int:
        return sum(b.tamano for b in self.bloques if b.libre)

    @property
    def usada(self) -> int:
        return self.total - self.libre

    @property
    def mayor_hueco(self) -> int:
        return max((b.tamano for b in self.bloques if b.libre), default=0)

    def huecos(self) -> list[Bloque]:
        return [b for b in self.bloques if b.libre]

    # ----------------------------------------------------------- asignación
    def _elegir_hueco(self, tamano: int) -> Bloque | None:
        candidatos = [b for b in self.bloques if b.libre and b.tamano >= tamano]
        if not candidatos:
            return None
        if self.estrategia == "best-fit":
            return min(candidatos, key=lambda b: b.tamano)
        if self.estrategia == "worst-fit":
            return max(candidatos, key=lambda b: b.tamano)
        return candidatos[0]  # first-fit: el primero (menor dirección)

    def asignar(self, pid: int, tamano: int) -> int:
        """Reserva `tamano` MB contiguos para `pid`. Devuelve la dirección base.

        Lanza MemoriaInsuficienteError si no existe un hueco suficiente.
        """
        if tamano <= 0:
            raise ValueError("El tamaño debe ser positivo")
        hueco = self._elegir_hueco(tamano)
        if hueco is None:
            if tamano > self.total:
                detalle = f"excede la RAM física total ({self.total} MB)"
            elif tamano <= self.libre:
                detalle = (f"hay {self.libre} MB libres pero fragmentados; "
                           f"el mayor hueco contiguo es de {self.mayor_hueco} MB "
                           f"(fragmentación externa)")
            else:
                detalle = f"solo hay {self.libre} MB libres"
            raise MemoriaInsuficienteError(
                f"OUT OF MEMORY: se solicitaron {tamano} MB y {detalle}")

        # Partir el hueco: la parte baja se asigna, el resto queda libre.
        idx = self.bloques.index(hueco)
        asignado = Bloque(hueco.inicio, tamano, pid)
        resto = hueco.tamano - tamano
        self.bloques[idx] = asignado
        if resto > 0:
            self.bloques.insert(idx + 1, Bloque(asignado.fin, resto))
        return asignado.inicio

    def liberar(self, pid: int) -> int:
        """Libera el bloque del proceso y fusiona huecos adyacentes."""
        liberado = 0
        for b in self.bloques:
            if b.pid == pid:
                liberado += b.tamano
                b.pid = None
        self._fusionar_huecos()
        return liberado

    def _fusionar_huecos(self) -> None:
        fusionados: list[Bloque] = []
        for b in self.bloques:
            if fusionados and fusionados[-1].libre and b.libre:
                fusionados[-1].tamano += b.tamano
            else:
                fusionados.append(b)
        self.bloques = fusionados

    def compactar(self) -> dict[int, int]:
        """Desplaza los bloques ocupados al inicio de la RAM.

        Devuelve {pid: nueva_direccion_base} para que el kernel actualice
        los PCB (reubicación dinámica).
        """
        nuevas: dict[int, int] = {}
        cursor = 0
        ocupados = []
        for b in self.bloques:
            if not b.libre:
                ocupados.append(Bloque(cursor, b.tamano, b.pid))
                nuevas[b.pid] = cursor
                cursor += b.tamano
        if cursor < self.total:
            ocupados.append(Bloque(cursor, self.total - cursor))
        self.bloques = ocupados
        return nuevas

    # ---------------------------------------------------------- presentación
    def mapa(self, ancho: int = 50) -> str:
        """Barra de texto proporcional: cada carácter ~ total/ancho MB."""
        escala = self.total / ancho
        celdas = []
        for b in self.bloques:
            n = max(1, round(b.tamano / escala))
            if b.libre:
                celdas.append("." * n)
            else:
                etiqueta = str(b.pid)
                relleno = "#" * max(0, n - len(etiqueta))
                celdas.append((etiqueta + relleno)[:n] if n >= len(etiqueta) else "#" * n)
        barra = "".join(celdas)[:ancho].ljust(ancho, ".")
        return f"|{barra}|"
