"""
demo.py - Casos de prueba guiados (no interactivos).

Reproduce los cuatro casos exigidos en la "Bitácora de Casos de Prueba":
  1. Rechazo de procesos por falta de RAM (Out of Memory).
  2. Sucesión de ráfagas en Round Robin (q = 3).
  3. Efectividad del semáforo ante condiciones de carrera.
  4. Detección y posterior eliminación de un Deadlock.

Se ejecuta con:  python main.py --demo      (o --demo 2 para un solo caso)
El generador del informe usa estas mismas funciones para que los volcados
de texto del PDF provengan del código real.
"""

from . import vistas
from .kernel import Kernel
from .memoria import MemoriaInsuficienteError
from .planificador import simular_rr_teorico


def titulo(texto: str) -> None:
    print("\n" + "=" * 72 + f"\n{texto}\n" + "=" * 72)


def caso_1_oom() -> None:
    titulo("CASO 1: Rechazo de procesos por falta de RAM (Out of Memory)")
    k = Kernel()
    k.crear_proceso("Navegador", 45, 6)
    k.crear_proceso("Editor", 30, 4)
    print("\n> Se intenta crear 'Juego' de 40 MB con solo 25 MB libres:")
    try:
        k.crear_proceso("Juego", 40, 5)
    except MemoriaInsuficienteError as e:
        print(f"  !!! {e}")
    print("\n> Se intenta crear un proceso de 150 MB (mayor que toda la RAM):")
    try:
        k.crear_proceso("Gigante", 150, 5)
    except MemoriaInsuficienteError as e:
        print(f"  !!! {e}")
    print("\n> Fragmentación externa: se termina 'Navegador' (libera 45 MB al inicio)")
    k.crear_proceso("Terminal", 20, 3)
    k.abortar(1, "cerrado por el usuario")
    print("> Hay 45 + 5 = 50 MB libres, pero en DOS huecos separados... se piden 50 MB:")
    try:
        k.crear_proceso("Compilador", 50, 4)
    except MemoriaInsuficienteError as e:
        print(f"  !!! {e}")
    print()
    print(vistas.mapa_memoria(k))
    print("\n> Tras compactar la memoria, el mismo proceso sí cabe:")
    k.compactar_memoria()
    k.crear_proceso("Compilador", 50, 4)
    print(vistas.mapa_memoria(k))


def caso_2_round_robin() -> None:
    titulo("CASO 2: Sucesión de ráfagas en Round Robin (q = 3)")
    k = Kernel()
    for nombre, mb, rafaga in (("P_Larga", 20, 10), ("P_Corta", 15, 4), ("P_Media", 25, 7)):
        k.crear_proceso(nombre, mb, rafaga)
    print(vistas.cola_listos(k))
    print()
    while k.planificador.hay_listos():
        k.ejecutar_turno()
        print("   " + vistas.cola_listos(k))
    k.ejecutar_turno()
    print()
    print(vistas.tabla_pcb(k))
    print("\nHilos (TCB) con el contexto guardado en cada cambio:")
    print(vistas.tabla_tcb(k))
    print()
    print(vistas.estadisticas(k))
    r = simular_rr_teorico([("P1", 10), ("P2", 4), ("P3", 7)], 3)
    print(f"\nComprobación con el cálculo teórico: espera promedio teórica = "
          f"{r['espera_promedio']:.2f}, simulada = {k.estadisticas()['espera_promedio']:.2f}")


def caso_3_semaforo() -> None:
    titulo("CASO 3: Efectividad del semáforo ante condiciones de carrera")
    k = Kernel()
    for nombre in ("Cajero1", "Cajero2", "Cajero3"):
        k.crear_proceso(nombre, 10, 6)
    print("\n> Parte A: carrera a nivel de instrucciones (LOAD / ADD / STORE)")
    sin, con = k.demo_condicion_carrera(2)
    print("\n  SIN semáforo:")
    print("\n".join("    " + t for t in sin["traza"]))
    print(f"  => valor final {sin['obtenido']} (esperado {sin['esperado']}): "
          f"{sin['perdidas']} actualizaciones perdidas")
    print("\n  CON semáforo binario:")
    print("\n".join("    " + t for t in con["traza"]))
    print(f"  => valor final {con['obtenido']} (esperado {con['esperado']}): "
          f"{con['perdidas']} actualizaciones perdidas")

    print("\n> Parte B: wait()/signal() con procesos del kernel y cola de espera")
    k.sc_wait(1)
    k.sc_escribir(1, 1)
    k.sc_wait(2)
    k.sc_wait(3)
    print("  " + vistas.estado_semaforo(k))
    try:
        k.sc_escribir(2, 1)
    except Exception as e:
        print(f"  ! {e}")
    print("  " + vistas.cola_listos(k))
    k.sc_signal(1)
    k.sc_escribir(2, 1)
    k.sc_signal(2)
    k.sc_escribir(3, 1)
    k.sc_signal(3)
    print("  " + vistas.estado_semaforo(k))


def caso_4_deadlock() -> None:
    titulo("CASO 4: Detección y posterior eliminación de un Deadlock")
    k = Kernel()
    k.forzar_deadlock()
    print()
    print(vistas.estado_recursos(k))
    print(vistas.tabla_pcb(k))
    print("\n> Intentar ejecutar: ambos procesos están bloqueados")
    k.ejecutar_turno()
    print("\n> Resolución: se aborta la víctima P2 (Proceso_B)")
    k.abortar(2, "víctima elegida para romper el interbloqueo")
    k.detectar_deadlock()
    print()
    print(vistas.estado_recursos(k))
    print("\n> Proceso_A continúa y termina normalmente:")
    k.ejecutar_todo()
    print(vistas.tabla_pcb(k))


CASOS = {1: caso_1_oom, 2: caso_2_round_robin, 3: caso_3_semaforo, 4: caso_4_deadlock}


def ejecutar_demo(caso: int | None = None) -> None:
    for numero, funcion in CASOS.items():
        if caso is None or caso == numero:
            funcion()
