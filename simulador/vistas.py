"""
vistas.py - Funciones de presentación en texto (tablas, mapas, diagramas).

Se separan de la consola para poder reutilizarlas en el modo demostración
y en el generador del informe.
"""

from .kernel import Kernel
from .pcb import Estado


def tabla(encabezados: list[str], filas: list[list]) -> str:
    filas = [[("-" if c is None else str(c)) for c in f] for f in filas]
    anchos = [len(h) for h in encabezados]
    for f in filas:
        for i, c in enumerate(f):
            anchos[i] = max(anchos[i], len(c))
    sep = "+" + "+".join("-" * (a + 2) for a in anchos) + "+"
    linea = lambda cols: "| " + " | ".join(c.ljust(a) for c, a in zip(cols, anchos)) + " |"
    salida = [sep, linea(encabezados), sep]
    salida += [linea(f) for f in filas] or ["| (vacío)".ljust(len(sep) - 1) + "|"]
    salida.append(sep)
    return "\n".join(salida)


def tabla_pcb(k: Kernel) -> str:
    filas = []
    for p in k.procesos.values():
        estado = p.estado.value + (" (abortado)" if p.abortado else "")
        if p.estado == Estado.BLOQUEADO:
            estado += f" [{p.motivo_bloqueo}]"
        filas.append([p.pid, p.nombre, estado, p.tamano_mb, p.direccion_base,
                      p.rafaga_total, p.rafaga_restante, p.cambios_contexto,
                      ",".join(f"R{r}" for r in sorted(p.recursos)) or None,
                      p.tiempo_espera])
    return tabla(["PID", "Nombre", "Estado", "MB", "Base", "Ráfaga", "Restante",
                  "Ctx", "Recursos", "Espera"], filas)


def tabla_tcb(k: Kernel) -> str:
    filas = []
    for p in k.procesos.values():
        for h in p.hilos:
            regs = " ".join(f"{r}={v}" for r, v in h.registros.items())
            filas.append([h.tid, p.pid, h.estado.value, h.contador_programa, regs])
    return tabla(["TID", "PID", "Estado", "PC", "Registros guardados"], filas)


def cola_listos(k: Kernel) -> str:
    cola = " <- ".join(f"P{p.pid}({p.rafaga_restante})" for p in k.planificador.cola_listos)
    return f"Cola de listos (frente -> final): {cola or '(vacía)'}"


def mapa_memoria(k: Kernel) -> str:
    m = k.memoria
    lineas = [f"RAM: {m.total} MB | usada {m.usada} MB | libre {m.libre} MB | "
              f"mayor hueco {m.mayor_hueco} MB | estrategia {m.estrategia}",
              m.mapa(), "  ('#' = ocupado, '.' = libre, número = PID al inicio de su bloque)"]
    filas = [[b.inicio, b.fin, b.tamano, "LIBRE" if b.libre else f"P{b.pid}"] for b in m.bloques]
    lineas.append(tabla(["Inicio", "Fin", "MB", "Contenido"], filas))
    return "\n".join(lineas)


def estado_semaforo(k: Kernel) -> str:
    s = k.seccion_critica.semaforo
    cola = "[" + ", ".join(f"P{p}" for p in s.cola_espera) + "]" if s.cola_espera else "(vacía)"
    duenio = f"P{s.duenio}" if s.duenio is not None else "nadie"
    return (f"Semáforo '{s.nombre}': valor={s.valor} | en sección crítica: {duenio} | "
            f"cola de espera: {cola} | variable global = {k.seccion_critica.variable_global}")


def estado_recursos(k: Kernel) -> str:
    filas = []
    for r in k.recursos.recursos.values():
        filas.append([r.nombre, f"P{r.asignado_a}" if r.asignado_a else "libre",
                      ", ".join(f"P{p}" for p in r.cola_espera) or None])
    grafo = k.recursos.grafo_espera()
    aristas = ", ".join(f"P{a}->P{b}" for a, bs in sorted(grafo.items()) for b in sorted(bs))
    return (tabla(["Recurso", "Asignado a", "Cola de espera"], filas)
            + f"\nGrafo de espera: {aristas or '(sin aristas)'}")


def estadisticas(k: Kernel) -> str:
    e = k.estadisticas()
    return (f"Reloj={e['reloj']} | creados={e['creados']} | rechazados OOM={e['rechazados_oom']} | "
            f"terminados={e['terminados']} | abortados={e['abortados']} | "
            f"cambios de contexto={e['cambios_contexto']}\n"
            f"Promedios (terminados): espera={e['espera_promedio']:.2f} | "
            f"retorno={e['retorno_promedio']:.2f} | respuesta={e['respuesta_promedio']:.2f}\n"
            f"Utilización de CPU={e['utilizacion_cpu']:.2f} % | "
            f"Rendimiento={e['rendimiento']:.3f} procesos/unidad de tiempo "
            f"({e['rendimiento'] * 100:.2f} % por unidad)\n"
            f"Utilización de RAM: actual={e['utilizacion_ram']:.2f} % | pico={e['pico_ram']:.2f} %\n"
            f"Diagrama de Gantt:\n{k.planificador.diagrama_gantt()}")
