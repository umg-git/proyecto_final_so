"""
main.py - Punto de entrada del Simulador de Funciones del Kernel.

Uso:
    python main.py            -> menú interactivo
    python main.py --demo     -> ejecuta los 4 casos de prueba de la bitácora
    python main.py --demo 3   -> ejecuta solo el caso 3
"""

import sys

from simulador.consola import ejecutar_consola
from simulador.demo import ejecutar_demo


def main() -> None:
    # Garantiza tildes y ñ correctas en la consola de Windows.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    args = sys.argv[1:]
    if args and args[0] == "--demo":
        caso = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        ejecutar_demo(caso)
    else:
        ejecutar_consola()


if __name__ == "__main__":
    main()
