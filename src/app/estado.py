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
import time

import streamlit as st

from nucleo.config import USUARIOS_DEFECTO

ROL_PUBLICO = "publico"
ROL_ADMIN = "admin"


def _secretos_existen() -> bool:
    """True si la app tiene CUALQUIER secreto configurado (es decir, la nube)."""
    try:
        return len(list(st.secrets.keys())) > 0
    except Exception:
        return False


def _normalizar_usuario(datos) -> dict:
    d = dict(datos) if hasattr(datos, "keys") else {"clave": str(datos)}
    return {"clave": str(d.get("clave", "")),
            "rol": str(d.get("rol", ROL_ADMIN)).lower().strip()}


def _usuarios() -> dict:
    """
    Administradores definidos en los Secrets de Streamlit. Forma correcta:

        [usuarios."director.promocion@sbcol.org"]
        clave = "..."
        rol   = "admin"

    TRES REGLAS, cada una nacida de un error real:

    1. Se acepta también la forma ["usuarios.NOMBRE"]. Es TOML válido pero
       crea una sección suelta llamada literalmente "usuarios.NOMBRE" en vez
       de una entrada dentro de [usuarios]. Esa forma la di YO, mal, en las
       instrucciones de la v2.0; quien la pegó quedó sin poder entrar. Leerla
       no es adivinar: la sección no tiene otro significado posible.
    2. El usuario de fábrica (config.USUARIOS_DEFECTO) SOLO vale cuando la
       app no tiene ningún secreto, o sea en un computador local de prueba.
       Hasta la v2.2 se usaba también en la nube cuando faltaba [usuarios],
       y su clave está escrita en el código: era una puerta abierta.
    3. Si hay secretos pero ningún usuario, se devuelve vacío: nadie entra,
       y la pantalla de acceso lo dice en vez de fallar en silencio.
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
        salida = {}
    if salida:
        return salida
    return {} if _secretos_existen() else dict(USUARIOS_DEFECTO)


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

    · El usuario se compara sin mayúsculas ni espacios de sobra (en el
      celular el corrector pone mayúscula inicial al correo).
    · Solo entra quien tenga rol "admin". Hasta la v2.2 no se miraba el rol
      y los usuarios "colaborador" de la plantilla vieja, con clave
      "CAMBIAR", entraban a la configuración.
    · La clave se compara en tiempo constante (hmac.compare_digest).
    """
    usuarios = _usuarios()
    entrada = str(usuario).strip().lower()
    match = next((u for u in usuarios if u.strip().lower() == entrada), None)
    valido = (
        match is not None
        and usuarios[match].get("rol") == ROL_ADMIN
        and hmac.compare_digest(str(clave).encode("utf-8"),
                                str(usuarios[match].get("clave", "")).encode("utf-8"))
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


def solo_admin() -> None:
    """
    Puerta de las páginas de administración. Si no hay sesión, muestra el
    formulario ahí mismo y detiene la página: no hay que irse a otro lado
    ni perder lo que se estaba haciendo.
    """
    if es_admin():
        return
    st.markdown("#### Entrar como administrador")
    st.caption("Esta parte es para configurar la app. Si solo querés usarla, "
               "volvé con los botones de abajo.")
    if not _usuarios():
        st.warning("No hay administradores configurados en los Secrets de la "
                   "app. Agregá la sección [usuarios] y reiniciá.")
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
