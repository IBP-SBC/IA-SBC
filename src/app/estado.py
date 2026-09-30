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

import streamlit as st

from nucleo.config import USUARIOS_DEFECTO

ROL_PUBLICO = "publico"
ROL_ADMIN = "admin"


def _usuarios() -> dict:
    """
    Usuarios desde st.secrets['usuarios']; si no hay, los de defecto.

        [usuarios."PEÑA JOSE ALBERTO"]
        clave = "..."
        rol   = "admin"
    """
    try:
        if "usuarios" in st.secrets:
            salida = {}
            for nombre, datos in dict(st.secrets["usuarios"]).items():
                d = dict(datos) if hasattr(datos, "keys") else {"clave": str(datos)}
                salida[str(nombre)] = {
                    "clave": str(d.get("clave", "")),
                    "rol": str(d.get("rol", ROL_ADMIN)).lower().strip(),
                }
            if salida:
                return salida
    except Exception:
        pass
    return dict(USUARIOS_DEFECTO)


def rol_actual() -> str:
    return ROL_ADMIN if st.session_state.get("_auth_ok") else ROL_PUBLICO


def es_admin() -> bool:
    return bool(st.session_state.get("_auth_ok"))


def usuario_actual() -> str:
    return str(st.session_state.get("_auth_user", "visitante"))


def entrar(usuario: str, clave: str) -> bool:
    """
    Valida credenciales. El usuario se compara sin distinguir mayúsculas
    ni espacios de sobra: nadie va a escribir "PEÑA JOSE ALBERTO" igual
    dos veces en un teclado de celular.
    """
    usuarios = _usuarios()
    entrada = str(usuario).strip().lower()
    match = next((u for u in usuarios if u.strip().lower() == entrada), None)
    if match and str(clave) == str(usuarios[match].get("clave", "")):
        st.session_state["_auth_ok"] = True
        st.session_state["_auth_user"] = match
        return True
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
    with st.form("_form_login"):
        usuario = st.text_input("Usuario", key="_inp_user",
                                placeholder="PEÑA JOSE ALBERTO")
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
