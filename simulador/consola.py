"""
consola.py - Interfaz de línea de comandos (menús de texto).

Toda entrada del usuario pasa por funciones de lectura con validación, de
modo que ningún valor aleatorio (texto, negativos, decimales, vacíos,
números gigantes, Ctrl+C) pueda romper el simulador durante la prueba de
estrés en vivo.
"""

import random

from . import config, vistas
from .kernel import ErrorKernel, Kernel
from .memoria import MemoriaInsuficienteError
from .planificador import simular_rr_teorico


class Cancelado(Exception):
    """El usuario dejó la entrada vacía o presionó Ctrl+C: volver al menú."""


# ============================================================ lectura segura
def leer_texto(mensaje: str) -> str:
    try:
        return input(mensaje).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Cancelado()


def leer_entero(mensaje: str, minimo: int, maximo: int, defecto: int | None = None) -> int:
    """Repite la pregunta hasta recibir un entero dentro de [minimo, maximo]."""
    sufijo = f" [{minimo}-{maximo}]" + (f" (Enter={defecto})" if defecto is not None else "")
    while True:
        texto = leer_texto(f"{mensaje}{sufijo}: ")
        if texto == "":
            if defecto is not None:
                return defecto
            raise Cancelado()
        try:
            valor = int(texto)
        except ValueError:
            print(f"  ! '{texto}' no es un número entero válido. Intente de nuevo (Enter vacío = cancelar).")
            continue
        if not minimo <= valor <= maximo:
            print(f"  ! El valor debe estar entre {minimo} y {maximo}.")
            continue
        return valor


def leer_pid(k: Kernel, mensaje: str = "PID") -> int:
    if not k.procesos:
        raise ErrorKernel("No hay procesos creados")
    return leer_entero(mensaje, 1, max(k.procesos))


def pausa() -> None:
    try:
        input("\n(Enter para continuar)")
    except (EOFError, KeyboardInterrupt):
        print()


# ================================================================== acciones
def accion_crear(k: Kernel) -> None:
    nombre = leer_texto(f"Nombre del proceso (Enter = automático, máx {config.NOMBRE_MAX}): ")
    tamano = leer_entero("Tamaño en memoria (MB)", config.TAMANO_MIN_MB, config.TAMANO_MAX_MB)
    rafaga = leer_entero("Ráfaga de CPU total", config.RAFAGA_MIN, config.RAFAGA_MAX)
    hilos = leer_entero("Número de hilos (TCB)", config.HILOS_MIN, config.HILOS_MAX, defecto=1)
    k.crear_proceso(nombre, tamano, rafaga, hilos)


def accion_aleatorios(k: Kernel) -> None:
    n = leer_entero("¿Cuántos procesos aleatorios?", 1, 50, defecto=5)
    for _ in range(n):
        try:
            k.crear_proceso("", random.randint(5, 40), random.randint(1, 15), random.randint(1, 3))
        except MemoriaInsuficienteError:
            pass  # el kernel ya registró el rechazo en la bitácora


def accion_teorico(k: Kernel) -> None:
    cola = list(k.planificador.cola_listos)
    if cola:
        datos = [(f"P{p.pid}", p.rafaga_restante) for p in cola]
        print("Cálculo sobre la cola de listos actual (ráfagas restantes, llegada relativa t=0):")
    else:
        datos = [("P1", 10), ("P2", 4), ("P3", 7)]
        print("Cola vacía; se usa el ejemplo del informe: P1=10, P2=4, P3=7")
    r = simular_rr_teorico(datos, k.planificador.quantum)
    print("Secuencia: " + " ".join(f"{n}[{a}-{b}]" for n, a, b in r["secuencia"]))
    print(vistas.tabla(["Proceso", "Ráfaga", "Fin", "Retorno", "Espera", "Respuesta"],
                       [[f["nombre"], f["rafaga"], f["fin"], f["retorno"], f["espera"], f["respuesta"]]
                        for f in r["filas"]]))
    print(f"Espera promedio = {r['espera_promedio']:.2f} | Retorno promedio = "
          f"{r['retorno_promedio']:.2f} | Respuesta promedio = {r['respuesta_promedio']:.2f} | "
          f"Cambios de contexto = {r['cambios_contexto']}")


def accion_carrera(k: Kernel) -> None:
    inc = leer_entero("Incrementos por participante", 1, 20, defecto=3)
    sin, con = k.demo_condicion_carrera(inc)
    print("\n--- SIN semáforo (intercalado a nivel de instrucción) ---")
    print("\n".join(sin["traza"][:18]) + ("\n..." if len(sin["traza"]) > 18 else ""))
    print(f"Resultado: {sin['obtenido']} (esperado {sin['esperado']}) -> "
          f"{sin['perdidas']} actualizaciones PERDIDAS")
    print("\n--- CON semáforo binario wait()/signal() ---")
    print("\n".join(con["traza"][:24]) + ("\n..." if len(con["traza"]) > 24 else ""))
    print(f"Resultado: {con['obtenido']} (esperado {con['esperado']}) -> "
          f"{con['perdidas']} actualizaciones perdidas")


# ================================================================== menús
MENU_PRINCIPAL = """
==================== SIMULADOR DE KERNEL - SO I ====================
 RAM {libre}/{total} MB libres | quantum q={q} | reloj t={reloj} | procesos vivos: {vivos}
--------------------------------------------------------------------
  1. Crear proceso (PCB/TCB)             7. Análisis teórico RR (tiempos de espera)
  2. Crear procesos aleatorios (estrés)  8. Concurrencia: semáforo / sección crítica
  3. Ver tabla de procesos PCB y TCB     9. Interbloqueo: recursos / deadlock
  4. Ver mapa de memoria RAM            10. Abortar (kill) un proceso
  5. Ejecutar UN quantum (Round Robin)  11. Estadísticas y diagrama de Gantt
  6. Ejecutar hasta vaciar la cola      12. Bitácora de eventos
 13. Compactar memoria                  14. Reiniciar simulador
  0. Salir
"""

MENU_SC = """
------------- CONCURRENCIA (Semáforo binario) -------------
{estado}
  1. wait()   - solicitar entrada a la sección crítica
  2. Modificar la variable global compartida (+1)
  3. signal() - salir de la sección crítica
  4. Demostración de condición de carrera (sin vs con semáforo)
  0. Volver
"""

MENU_DL = """
------------- INTERBLOQUEO (Recurso 1 / Recurso 2) -------------
{estado}
  1. Solicitar recurso          4. FORZAR deadlock (Proceso A / Proceso B)
  2. Liberar recurso            5. Detectar deadlock
  3. Ver procesos               6. Abortar proceso (resolver deadlock)
  0. Volver
"""


def submenu_concurrencia(k: Kernel) -> None:
    while True:
        print(MENU_SC.format(estado=vistas.estado_semaforo(k)))
        op = leer_entero("Opción", 0, 4)
        try:
            if op == 0:
                return
            if op == 1:
                k.sc_wait(leer_pid(k))
            elif op == 2:
                k.sc_escribir(leer_pid(k), 1)
            elif op == 3:
                k.sc_signal(leer_pid(k))
            elif op == 4:
                accion_carrera(k)
                pausa()
        except ErrorKernel as e:
            print(f"  ! {e}")


def submenu_deadlock(k: Kernel) -> None:
    while True:
        print(MENU_DL.format(estado=vistas.estado_recursos(k)))
        op = leer_entero("Opción", 0, 6)
        try:
            if op == 0:
                return
            if op == 1:
                k.solicitar_recurso(leer_pid(k), leer_entero("Recurso", 1, 2))
            elif op == 2:
                k.liberar_recurso(leer_pid(k), leer_entero("Recurso", 1, 2))
            elif op == 3:
                print(vistas.tabla_pcb(k))
            elif op == 4:
                k.forzar_deadlock()
            elif op == 5:
                k.detectar_deadlock()
            elif op == 6:
                pid = leer_pid(k, "PID de la víctima")
                k.abortar(pid, "víctima elegida para romper el interbloqueo")
                k.detectar_deadlock()
        except (ErrorKernel, MemoriaInsuficienteError, ValueError) as e:
            print(f"  ! {e}")


def ejecutar_consola() -> None:
    k = Kernel()
    print("Simulador de Funciones del Kernel - Proyecto individual - Universidad Mariano Gálvez de Guatemala")
    while True:
        print(MENU_PRINCIPAL.format(libre=k.memoria.libre, total=k.memoria.total,
                                    q=k.planificador.quantum, reloj=k.reloj, vivos=len(k.vivos())))
        try:
            op = leer_entero("Opción", 0, 14)
        except Cancelado:
            op = 0
        try:
            if op == 0:
                print("Apagando el simulador... ¡Hasta luego!")
                return
            elif op == 1:
                accion_crear(k)
            elif op == 2:
                accion_aleatorios(k)
            elif op == 3:
                print(vistas.tabla_pcb(k))
                print(vistas.cola_listos(k))
                print("\nHilos (TCB):")
                print(vistas.tabla_tcb(k))
                pausa()
            elif op == 4:
                print(vistas.mapa_memoria(k))
                pausa()
            elif op == 5:
                k.ejecutar_turno()
                print(vistas.cola_listos(k))
            elif op == 6:
                k.ejecutar_todo()
            elif op == 7:
                accion_teorico(k)
                pausa()
            elif op == 8:
                submenu_concurrencia(k)
            elif op == 9:
                submenu_deadlock(k)
            elif op == 10:
                k.abortar(leer_pid(k))
            elif op == 11:
                print(vistas.estadisticas(k))
                pausa()
            elif op == 12:
                print("\n".join(k.bitacora[-60:]) or "(bitácora vacía)")
                pausa()
            elif op == 13:
                k.compactar_memoria()
            elif op == 14:
                k = Kernel()
                print("Simulador reiniciado.")
        except Cancelado:
            print("  (operación cancelada)")
        except MemoriaInsuficienteError as e:
            print(f"  !!! {e}")
        except (ErrorKernel, ValueError) as e:
            print(f"  ! {e}")
