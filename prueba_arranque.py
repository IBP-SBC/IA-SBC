"""
prueba_arranque.py
==================
Comprueba que la app ARRANCA de verdad: el login, y CADA página, con rol
admin y con rol colaborador. Usa AppTest, que corre Streamlit sin
navegador.

POR QUÉ una por una: con st.navigation, abrir Home solo ejecuta la
página por defecto. Una página que truena al abrirse es justo el primer
error que vería el usuario, y no lo veríamos acá si probáramos solo Home.

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
_FALLOS: list[str] = []


def _correr(ruta: Path, rol: str | None) -> AppTest:
    """Ejecuta un script de Streamlit. rol=None simula sesión cerrada."""
    at = AppTest.from_file(str(ruta), default_timeout=60)
    if rol:
        at.session_state["_auth_ok"] = True
        at.session_state["_auth_user"] = "prueba"
        at.session_state["_auth_rol"] = rol
    at.run()
    return at


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    if condicion:
        print(f"  ✓ {nombre}")
    else:
        _FALLOS.append(f"{nombre} — {detalle}")
        print(f"  ✗ {nombre} → {detalle}")


print("\n═══ ARRANQUE ═══")

at = _correr(HOME, None)
# Se comprueba por los CAMPOS, no por el texto: el texto del encabezado
# puede cambiar con el diseño y la prueba seguiría siendo válida.
check("Sin sesión muestra el formulario y no truena",
      not at.exception and len(at.text_input) >= 2,
      str(at.exception) or f"campos encontrados: {len(at.text_input)}")

for rol in ("admin", "colaborador"):
    at = _correr(HOME, rol)
    check(f"Home abre con rol {rol}", not at.exception, str(at.exception))

for archivo in ("conversacion.py", "documentos.py", "instrucciones.py"):
    at = _correr(PAGINAS / archivo, "admin")
    check(f"La página {archivo} abre sin excepción",
          not at.exception, str(at.exception))

at = _correr(PAGINAS / "documentos.py", "colaborador")
check("Un colaborador NO entra a Documentos",
      bool(at.warning), "no se mostró la advertencia de permisos")

at = _correr(PAGINAS / "instrucciones.py", "colaborador")
check("Un colaborador NO edita las instrucciones",
      bool(at.warning), "no se mostró la advertencia de permisos")

print("\n" + "═" * 60)
if _FALLOS:
    print(f"FALLARON {len(_FALLOS)} pruebas\n")
    for f in _FALLOS:
        print(f"  ✗ {f}")
    sys.exit(1)
print("Todas las pruebas de arranque pasaron.")
