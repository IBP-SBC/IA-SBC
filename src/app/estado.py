"""
app/estado.py
=============
Quién entra y con qué permisos.

EL CAMBIO DE LA v2: la app dejó de estar cerrada. Cualquiera puede entrar
y usarla —conversar sobre la Biblia, leer, cotizar— sin clave y sin
registro. La clave quedó SOLO para administrar.

Por qué tiene sentido y no es un descuido: lo que ve el visitante son
temas bíblicos y productos; lo que está detrás de la clave son los
documentos internos (planes, presupuestos, estrategia), la lista de
precios y los textos. La barrera no está en la puerta de la app: está
entre los dos corpus (ver nucleo/indice.py) y en las páginas de
administración.

REGLA: exigir_login() ya no existe. Una página de administración llama a
`solo_admin()` al principio; una página pública no llama a nada.
"""
from __future__ import annotations

import hmac
import os
import re
import time
import unicodedata

import streamlit as st

from nucleo.config import APP_VERSION

ROL_PUBLICO = "publico"
ROL_ADMIN = "admin"


def _rutas_secrets() -> list[str]:
    """Dónde busca Streamlit el archivo de Secrets (nube y computador)."""
    try:
        from streamlit import config as _st_config
        rutas = _st_config.get_option("secrets.files") or []
    except Exception:
        rutas = []
    return [os.path.expanduser(str(r)) for r in rutas]


def estado_secrets() -> dict:
    """
    ¿Puede la app leer sus Secrets? Tres respuestas posibles:

      {"estado": "ok"}                         se leyeron
      {"estado": "sin_secrets"}                no hay ningún archivo
      {"estado": "ilegibles", "linea": N}      existen, pero con un error
                                               de formato (N puede ser None)

    POR QUÉ IMPORTA DISTINGUIRLAS (error mío de la v2.3.0): la app trataba
    "ilegibles" igual que "no hay", y en ese caso habilitaba el usuario de
    fábrica, cuya clave está en el código público de GitHub. Y quien tenía
    la clave correcta solo veía "Usuario o clave incorrectos", sin pista.
    Al pegar Secrets en un iPad lo más común es exactamente esto: comillas
    curvas en vez de rectas, o el bloque repetido.

    Del error se muestra SOLO el número de línea: el mensaje del lector de
    TOML puede citar valores de los Secrets, claves incluidas.
    """
    try:
        list(st.secrets.keys())
        return {"estado": "ok"}
    except Exception as e:
        if not any(os.path.exists(r) for r in _rutas_secrets()):
            return {"estado": "sin_secrets"}
        # El lector cambia entre versiones de Streamlit y con él el mensaje:
        # "(line 1 column 1 char 0)" en la 1.57, "(at line 1, column 11)"
        # en la 1.66. Se toma la última mención de línea.
        lineas = re.findall(r"line (\d+),? column \d+", str(e))
        return {"estado": "ilegibles", "linea": int(lineas[-1]) if lineas else None}


def _normalizar_usuario(datos) -> dict:
    d = dict(datos) if hasattr(datos, "keys") else {"clave": str(datos)}
    return {"clave": str(d.get("clave", "")),
            "rol": str(d.get("rol", ROL_ADMIN)).lower().strip()}


def _usuarios() -> dict:
    """
    Usuarios definidos en los Secrets de Streamlit. Forma correcta:

        [usuarios."director.promocion@sbcol.org"]
        clave = "..."
        rol   = "admin"

    TRES REGLAS, cada una nacida de un error real:

    1. Se acepta también la forma ["usuarios.NOMBRE"]. Es TOML válido pero
       crea una sección suelta llamada literalmente "usuarios.NOMBRE" en vez
       de una entrada dentro de [usuarios]. Esa forma la di YO, mal, en las
       instrucciones de la v2.0; quien la pegó quedó sin poder entrar. Leerla
       no es adivinar: la sección no tiene otro significado posible.
    2. NO HAY USUARIO DE FÁBRICA (v2.3.1). Existió para el primer arranque
       en un computador y abrió dos huecos: hasta la v2.2 valía en la nube
       cuando faltaba [usuarios], y en la v2.3.0 cuando los Secrets no se
       podían leer. Sin Secrets legibles, nadie entra, y la pantalla de
       acceso dice por qué.
    3. Si algo falla al leer, se devuelve vacío: nunca un usuario a medias.
    """
    salida: dict = {}
    try:
        if "usuarios" in st.secrets:
            for nombre, datos in dict(st.secrets["usuarios"]).items():
                salida[str(nombre)] = _normalizar_usuario(datos)
        for seccion in list(st.secrets.keys()):
            seccion = str(seccion)
            if seccion.startswith("usuarios.") and len(seccion) > len("usuarios."):
                salida[seccion[len("usuarios."):]] = _normalizar_usuario(
                    st.secrets[seccion])
    except Exception:
        return {}
    return salida


def _administradores() -> dict:
    return {u: d for u, d in _usuarios().items() if d.get("rol") == ROL_ADMIN}


def _forma_de_comparar(usuario: str) -> str:
    """
    Cómo se comparan los USUARIOS: sin mayúsculas, sin tildes y sin
    espacios. El teclado del celular pone mayúscula inicial al correo, el
    corrector puede escribir "promoción" donde va "promocion" y una
    sugerencia deja un espacio al final; ninguna de esas diferencias
    distingue a dos personas. La CLAVE, en cambio, se compara exacta.
    """
    t = unicodedata.normalize("NFKD", str(usuario))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(t.lower().split())


def rol_actual() -> str:
    return ROL_ADMIN if st.session_state.get("_auth_ok") else ROL_PUBLICO


def es_admin() -> bool:
    return bool(st.session_state.get("_auth_ok"))


def usuario_actual() -> str:
    return str(st.session_state.get("_auth_user", "visitante"))


# Pausa tras un intento fallido. No impide adivinar, pero convierte miles
# de intentos por minuto en unos cuarenta: vuelve inviable probar claves a
# ciegas contra una dirección pública.
PAUSA_INTENTO_FALLIDO = 1.5


def entrar(usuario: str, clave: str) -> bool:
    """
    Valida credenciales de ADMINISTRADOR.

    · El usuario se compara sin mayúsculas, tildes ni espacios (ver
      _forma_de_comparar).
    · Solo entra quien tenga rol "admin". Hasta la v2.2 no se miraba el rol
      y los usuarios "colaborador" de la plantilla vieja, con clave
      "CAMBIAR", entraban a la configuración.
    · La clave se compara exacta y en tiempo constante (hmac.compare_digest).
    """
    admins = _administradores()
    entrada = _forma_de_comparar(usuario)
    match = next((u for u in admins if _forma_de_comparar(u) == entrada), None)
    valido = (
        match is not None
        and hmac.compare_digest(str(clave).encode("utf-8"),
                                str(admins[match].get("clave", "")).encode("utf-8"))
    )
    if valido:
        st.session_state["_auth_ok"] = True
        st.session_state["_auth_user"] = match
        return True
    time.sleep(PAUSA_INTENTO_FALLIDO)
    return False


def salir() -> None:
    """Cierra la sesión de administrador; la app sigue funcionando."""
    for k in ("_auth_ok", "_auth_user"):
        st.session_state.pop(k, None)


def _pie_acceso(n_admins: int) -> None:
    """Versión y cuántos administradores leyó la app (sin nombres ni claves).
    Responde de un vistazo las dos primeras preguntas de cualquier problema
    de acceso: ¿llegó la versión nueva? ¿llegaron los Secrets?"""
    st.caption(f"IA-SBC {APP_VERSION} · administradores leídos de los Secrets: {n_admins}")


def solo_admin() -> None:
    """
    Puerta de las páginas de administración. Si no hay sesión, muestra el
    formulario ahí mismo y detiene la página: no hay que irse a otro lado
    ni perder lo que se estaba haciendo.

    Si nadie puede entrar, lo dice y dice POR QUÉ, en vez de mostrar un
    formulario que siempre contesta "incorrecto".
    """
    if es_admin():
        return
    st.markdown("#### Entrar como administrador")
    st.caption("Esta parte es para configurar la app. Si solo querés usarla, "
               "volvé con los botones de abajo.")

    diag = estado_secrets()
    if diag["estado"] == "ilegibles":
        cerca = f" (cerca de la línea {diag['linea']})" if diag.get("linea") else ""
        st.error(
            f"**La app no puede leer sus Secrets: tienen un error de formato{cerca}.** "
            "Mientras no se corrija, nadie puede entrar y la app tampoco puede "
            "conectarse a Supabase ni al modelo.\n\n"
            "Lo más común: comillas curvas (“ ”) en vez de rectas (\"), un bloque "
            "pegado dos veces o el correo sin comillas. Corregilo en "
            "share.streamlit.io → la app → Settings → Secrets, guardá y hacé Reboot.")
        _pie_acceso(0)
        st.stop()

    admins = _administradores()
    if not admins:
        if diag["estado"] == "sin_secrets":
            st.warning(
                "Esta copia de la app no tiene Secrets, así que no hay "
                "administradores. En la nube se configuran en Settings → "
                "Secrets. En un computador, copiá `.streamlit/secrets.toml.ejemplo` "
                "como `.streamlit/secrets.toml` y poné una clave.")
        else:
            st.warning(
                "No hay administradores configurados en los Secrets de la app. "
                "Agregá el bloque `[usuarios.\"tu correo\"]` con `clave` y "
                "`rol = \"admin\"`, guardá y hacé Reboot.")
        _pie_acceso(0)
        st.stop()

    with st.form("_form_login"):
        usuario = st.text_input("Usuario", key="_inp_user",
                                placeholder="correo@sbcol.org")
        clave = st.text_input("Clave", type="password", key="_inp_pass")
        ok = st.form_submit_button("Entrar", use_container_width=True,
                                   type="primary")
    if ok:
        if entrar(usuario, clave):
            st.rerun()
        st.error("Usuario o clave incorrectos.")
        st.caption("El usuario es el correo completo. En la clave cuentan las "
                   "mayúsculas, y el número 0 no es la letra O. Si el teclado "
                   "la completó solo, borrala y escribila de nuevo.")
    _pie_acceso(len(admins))
    st.stop()


def encabezado_carga(titulo: str, estado: str, resumen: str,
                     ultima: str | None, ayuda: str) -> None:
    """
    ESTÁNDAR ÚNICO de los módulos de carga: siempre el mismo orden y las
    mismas palabras. Título → estado + resumen → última carga → ayuda.
    """
    from nucleo.util import sello_legible

    st.markdown(f"#### {titulo}")
    st.markdown(f"{estado} {resumen}".strip())
    st.caption(f"Última actualización: {sello_legible(ultima)}")
    with st.expander("¿Cómo funciona?"):
        st.markdown(ayuda)
