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
        at.session_state["_auth_user"] = "director.promocion@sbcol.org"
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

# La demo Millca: las tres pantallas, como visitante.
MILLCA = RAIZ / "src/app/millca"
for archivo in ("palabra.py", "inspiracion.py", "altar.py"):
    at = _correr(MILLCA / archivo)
    check(f"millca/{archivo} abre sin excepción", not at.exception,
          str(at.exception))

at = _correr(MILLCA / "palabra.py")
check("La Palabra muestra texto bíblico real",
      any("Verbo" in str(m.value) for m in at.markdown),
      "no apareció Juan 1 en pantalla")

# Un st.exception dentro de la página NO es at.exception: la página
# "abre" pero muestra un bloque rojo. Así se coló un TypeError de
# st.iframe que la prueba anterior daba por bueno.
at = _correr(MILLCA / "inspiracion.py")
check("Inspiración renderiza sin bloques de error en pantalla",
      not at.exception and len(at.error) == 0 and len(at.get("exception")) == 0,
      f"errores: {[str(e.value)[:80] for e in at.error]} "
      f"excepciones: {[str(e.value)[:80] for e in at.get('exception')]}")


# ════════════════════════════════════════════════════════════════════
# PRUEBAS QUE HACEN CLICS (v2.3)
# Hasta la v2.2 estas pruebas solo abrían las páginas. Así sobrevivió un
# error grave: los botones Anterior/Siguiente de las dos Biblias nunca
# cambiaron de capítulo. Una página que "abre" no es una página que sirve.
# ════════════════════════════════════════════════════════════════════
print("\n═══ NAVEGACIÓN ═══")


def _titulo(at, marca):
    for m in at.markdown:
        s = str(m.value)
        if marca in s:
            return s
    return ""


def _salto(at) -> str:
    """El bloque que lleva la pantalla al comienzo del capítulo ('' si no hay).
    Que el navegador de verdad se desplace se verificó aparte, con Playwright."""
    bloques = [str(h.proto.body) for h in at.get("html") if "scrollTop" in str(h.proto.body)]
    return bloques[0] if bloques else ""


at = _correr(MILLCA / "palabra.py")
check("Millca: al abrir NO se mueve la pantalla", _salto(at) == "")
[b for b in at.button if b.key == "_ml_sig"][0].click().run()
check("Millca: tras 'Siguiente' la pantalla va al comienzo de la lectura",
      ".ml-lectura" in _salto(at))
[b for b in at.button if b.key == "_ml_sig"][0].click().run()
check("Millca: 'Siguiente' dos veces lleva a Juan 3", "<h3>Juan 3</h3>" in _titulo(at, "<h3>Juan"),
      _titulo(at, "<h3>Juan")[:80])
[b for b in at.button if b.key == "_ml_ant"][0].click().run()
check("Millca: 'Anterior' vuelve a Juan 2", "<h3>Juan 2</h3>" in _titulo(at, "<h3>Juan"))
[b for b in at.button if b.key == "_ml_letra_A++"][0].click().run()
check("Millca: cambiar el tamaño de letra NO mueve la pantalla (no cambió el capítulo)",
      _salto(at) == "" and "<h3>Juan 2</h3>" in _titulo(at, "<h3>Juan"))

at = _correr(PAGINAS / "biblia.py")
check("Biblia: arranca en Mateo 1 con el texto de ejemplo",
      _titulo(at, "### ") == "### Mateo 1"
      and any("Reina-Valera 1909" in str(m.value) for m in at.markdown))
check("Biblia: al abrir NO se mueve la pantalla", _salto(at) == "")
at.selectbox(key="_bib_capitulo").set_value(28).run()
[b for b in at.button if b.key == "_bib_sig"][0].click().run()
check("Biblia: 'Siguiente' en Mateo 28 cruza a Marcos 1", _titulo(at, "### ") == "### Marcos 1",
      _titulo(at, "### "))
check("Biblia: tras 'Siguiente' la pantalla va al comienzo del capítulo",
      ".st-key-bib_capitulo" in _salto(at))
at.selectbox(key="_bib_libro").set_value("Filipenses").run()
check("Biblia: al cambiar de libro arranca en el capítulo 1",
      _titulo(at, "### ") == "### Filipenses 1")
at.text_input(key="_bib_buscar").set_value("todo lo puedo").run()
check("Biblia: escribir en el buscador NO mueve la pantalla (no cambió el capítulo)",
      _salto(at) == "")
[b for b in at.button if b.key.startswith("_bib_h_")][0].click().run()
check("Biblia: tocar un resultado de búsqueda abre ese capítulo",
      _titulo(at, "### ") == "### Filipenses 4")
check("Biblia: y lleva la pantalla a su comienzo", ".st-key-bib_capitulo" in _salto(at))
check("Biblia: ninguna excepción en todo el recorrido", not at.exception, str(at.exception))

print("\n═══ ACCESO DE ADMINISTRADOR ═══")
CLAVE_PRUEBA = "clave-de-prueba"        # NUNCA la real: esto va al repositorio


def _login(secretos: dict, usuario: str, clave: str) -> AppTest:
    at = AppTest.from_file(str(PAGINAS / "administrar.py"), default_timeout=60)
    for k, v in secretos.items():
        at.secrets[k] = v
    at.run()
    if at.text_input:
        at.text_input(key="_inp_user").set_value(usuario)
        at.text_input(key="_inp_pass").set_value(clave)
        [b for b in at.button if b.label == "Entrar"][0].click().run()
    return at


def _adentro(at) -> bool:
    return any(tb.label == "Precios" for tb in at.tabs)


SECRETOS_OK = {"usuarios": {"director.promocion@sbcol.org": {"clave": CLAVE_PRUEBA, "rol": "admin"}},
               "supabase": {"url": "", "key": ""}}
at = _login(SECRETOS_OK, " Director.Promocion@SBCOL.org ", CLAVE_PRUEBA)
check("Entra el administrador (aunque el correo venga con mayúsculas y espacios)", _adentro(at))
at = _login(SECRETOS_OK, "director.promocion@sbcol.org", "otra")
check("Con clave equivocada NO entra y lo dice",
      not _adentro(at) and any("incorrectos" in str(e.value) for e in at.error))
at = _login(SECRETOS_OK, "admin", "cambiar-en-secrets")
check("El usuario de fábrica NO entra cuando hay Secrets (era una puerta abierta)",
      not _adentro(at))
at = _login({"usuarios": {"diana": {"clave": "CAMBIAR", "rol": "colaborador"}},
             "supabase": {"url": ""}}, "diana", "CAMBIAR")
check("Un usuario 'colaborador' NO entra a la configuración", not _adentro(at))
at = _login({"usuarios.director.promocion@sbcol.org": {"clave": CLAVE_PRUEBA, "rol": "admin"},
             "supabase": {"url": ""}}, "director.promocion@sbcol.org", CLAVE_PRUEBA)
check("La sintaxis equivocada de la v2.0 también funciona (quien la pegó no queda afuera)",
      _adentro(at))
at = _login({"supabase": {"url": ""}}, "x", "y")
check("Sin administradores en los Secrets, la pantalla lo dice en vez de fallar mudo",
      any("No hay administradores" in str(w.value) for w in at.warning))

print("\n═══ COTIZADOR CON LA LISTA DE PRUEBA ═══")
# Se trabaja en una carpeta temporal: la prueba NO puede dejar archivos en
# data/estado del repositorio.
import tempfile  # noqa: E402
from nucleo import cotizador  # noqa: E402

_tmp = Path(tempfile.mkdtemp(prefix="cotizador_prueba_"))
_orig = (cotizador.ESTADO_DIR, cotizador.RUTA_PRECIOS, cotizador.RUTA_ADICIONALES)
cotizador.ESTADO_DIR = _tmp
cotizador.RUTA_PRECIOS = _tmp / "precios.parquet"
cotizador.RUTA_ADICIONALES = _tmp / "precios_adicionales.parquet"
try:
    ok, msg = cotizador.cargar_lista_de_prueba("prueba")
    at = _correr(PAGINAS / "personalizar.py")
    check("Con la lista de prueba, la pantalla pública lo avisa arriba",
          any("Precios de prueba" in str(w.value) for w in at.warning))
    check("800 Biblias RVR: $ 33.600.000 en pantalla",
          any("$ 33.600.000" in str(m.value) for m in at.markdown))
    at.multiselect(key="_cot_adic").set_value(
        ["Hoja de inserto personalizada", "Plancha de estampado de la cubierta"]).run()
    check("Con inserto y plancha: $ 35.150.000",
          any("$ 35.150.000" in str(m.value) for m in at.markdown))
    at.selectbox(key="_cot_familia").set_value("Tratado").run()
    check("Al cambiar a Tratado, la cantidad salta a su mínimo (5.000) y se limpian los agregados",
          at.number_input(key="_cot_cantidad").value == 5000
          and any("$ 900.000" in str(m.value) for m in at.markdown)
          and not [m for m in at.multiselect if m.key == "_cot_adic"])
    at.selectbox(key="_cot_familia").set_value("Producto propio").run()
    check("'Producto propio' se cotiza a pedido",
          any("a pedido" in str(i.value) for i in at.info))
    check("El cotizador no lanzó ninguna excepción", not at.exception, str(at.exception))
finally:
    cotizador.ESTADO_DIR, cotizador.RUTA_PRECIOS, cotizador.RUTA_ADICIONALES = _orig

print("\n" + "═" * 60)
if _FALLOS:
    print(f"FALLARON {len(_FALLOS)} pruebas\n")
    for f in _FALLOS:
        print(f"  ✗ {f}")
    sys.exit(1)
print("Todas las pruebas de arranque pasaron.")
