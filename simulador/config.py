"""
config.py - Parámetros globales del simulador.

Todos los valores "mágicos" del enunciado viven aquí para que puedan
modificarse en un solo lugar (por ejemplo, durante la prueba de estrés).
El simulador NO usa red, puertos ni claves de API: es una aplicación de
consola 100 % local que solo depende de la biblioteca estándar de Python.
"""

# --- Gestión de memoria -------------------------------------------------------
RAM_TOTAL_MB = 100            # Memoria física simulada (requerimiento B)
ESTRATEGIA_MEMORIA = "first-fit"   # first-fit | best-fit | worst-fit

# --- Planificación ------------------------------------------------------------
QUANTUM = 3                   # Quantum fijo del Round Robin (requerimiento A)

# --- Límites de validación de entradas (robustez ante la prueba de estrés) ---
TAMANO_MIN_MB = 1
TAMANO_MAX_MB = 1024          # Se permite pedir más de 100 MB para provocar el OOM
RAFAGA_MIN = 1
RAFAGA_MAX = 999
HILOS_MIN = 1
HILOS_MAX = 8
NOMBRE_MAX = 20

# --- Recursos exclusivos (requerimiento D) -----------------------------------
RECURSOS = {1: "Recurso 1", 2: "Recurso 2"}
