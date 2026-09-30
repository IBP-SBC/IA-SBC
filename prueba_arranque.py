"""
prueba_arranque.py
==================
Comprueba que la app ARRANCA de verdad: cada pantalla, como visitante sin
clave y como administrador. Usa AppTest, que corre Streamlit sin navegador.

POR QUÉ una por una: con la navegación oculta, abrir Home solo ejecuta la
pantalla por defecto. Una pantalla que truena al abrirse es justo el
primer error que vería el usuario.

Orden de validación antes de subir a GitHub:
    python3 validar_ast.py && python3 auditoria_iasbc.py && python3 prueba_arranque.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from streamlit.testing.v1 import AppTest  # noqa: E402

HOME = RAIZ / "src/app/Home.py"
PAGINAS = RAIZ / "src/app/paginas"
PUBLICAS = ("conversar.py", "biblia.py", "personalizar.py")
_FALLOS: list[str] = []


def _correr(ruta: Path, como_admin: bool = False) -> AppTest:
    """Ejecuta un script de Streamlit. Sin admin = visitante sin clave."""
    at = AppTest.from_file(str(ruta), default_timeout=60)
    if como_admin:
        at.session_state["_auth_ok"] = True
        at.session_state["_auth_user"] = "PEÑA JOSE ALBERTO"
    at.run()
    return at


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    if condicion:
        print(f"  ✓ {nombre}")
    else:
        _FALLOS.append(f"{nombre} — {detalle}")
        print(f"  ✗ {nombre} → {detalle}")


print("\n═══ ARRANQUE ═══")

at = _correr(HOME)
check("La app abre sin clave", not at.exception, str(at.exception))

at = _correr(HOME, True)
check("La app abre con sesión de administrador", not at.exception,
      str(at.exception))

for archivo in PUBLICAS:
    at = _correr(PAGINAS / archivo)
    check(f"{archivo} abre sin clave", not at.exception, str(at.exception))
    at = _correr(PAGINAS / archivo, True)
    check(f"{archivo} abre con clave", not at.exception, str(at.exception))

at = _correr(PAGINAS / "administrar.py")
check("Administrar pide clave en vez de mostrar la configuración",
      not at.exception and len(at.text_input) >= 2,
      str(at.exception) or "no apareció el formulario")

at = _correr(PAGINAS / "administrar.py", True)
check("Administrar abre con sesión iniciada", not at.exception,
      str(at.exception))

print("\n" + "═" * 60)
if _FALLOS:
    print(f"FALLARON {len(_FALLOS)} pruebas\n")
    for f in _FALLOS:
        print(f"  ✗ {f}")
    sys.exit(1)
print("Todas las pruebas de arranque pasaron.")
