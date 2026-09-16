"""
app/estado.py
=============
Sesión, roles y los widgets que comparten todas las páginas.

REGLA: exigir_login() se llama UNA sola vez, desde Home.py. Si una página
la vuelve a llamar, se duplica la key del botón "Salir" y Streamlit
revienta con DuplicateElementKey (ya pasó en sbc_ventas con Editorial).
"""
from __future__ import annotations

import streamlit as st

from nucleo.config import APP_NOMBRE, USUARIOS_DEFECTO
from nucleo.util import sello_legible


def _usuarios() -> dict:
    """
    Usuarios desde st.secrets['usuarios']; si no hay, los de defecto.

    Formato en Secrets:
        [usuarios.alberto]
        clave = "..."
        rol   = "admin"
    """
    try:
        if "usuarios" in st.secrets:
            crudo = st.secrets["usuarios"]
            salida = {}
            for nombre, datos in dict(crudo).items():
                d = dict(datos) if hasattr(datos, "keys") else {"clave": str(datos)}
                salida[str(nombre)] = {
                    "clave": str(d.get("clave", "")),
                    "rol": str(d.get("rol", "colaborador")).lower().strip(),
                }
            if salida:
                return salida
    except Exception:
        pass
    return dict(USUARIOS_DEFECTO)


def exigir_login() -> None:
    """Muestra el formulario y detiene la ejecución si no hay sesión."""
    if st.session_state.get("_auth_ok"):
        _sidebar_sesion()
        return

    st.markdown(f"## 🔐 {APP_NOMBRE} · Iniciar sesión")
    st.caption("Ingresá tu usuario y clave para entrar.")
    with st.form("_form_login"):
        usuario = st.text_input("Usuario", key="_inp_user")
        clave = st.text_input("Clave", type="password", key="_inp_pass")
        ok = st.form_submit_button("Ingresar", use_container_width=True)

    if ok:
        usuarios = _usuarios()
        entrada = str(usuario).strip().lower()
        match = next((u for u in usuarios if u.strip().lower() == entrada), None)
        if match and str(clave) == str(usuarios[match].get("clave", "")):
            st.session_state.clear()          # cada usuario arranca limpio
            st.session_state["_auth_ok"] = True
            st.session_state["_auth_user"] = match
            st.session_state["_auth_rol"] = usuarios[match].get("rol", "colaborador")
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos.")

    with st.expander("¿Qué es esta app?"):
        st.markdown(
            "Es el asistente de la SBC: responde preguntas del día a día "
            "**con base en los documentos oficiales** (planes, informes, "
            "estudios Patmos, estrategias) y siempre dice de qué documento "
            "sacó cada cosa. Si necesitás acceso, pedíselo al equipo de "
            "Planeación Integrada."
        )
    st.stop()


def _sidebar_sesion() -> None:
    """Usuario, rol, estado de la nube y botón de salir."""
    from nucleo import nube

    with st.sidebar:
        c1, c2 = st.columns([3, 2])
        c1.caption(f"👤 {st.session_state.get('_auth_user', '')}")
        if c2.button("Salir", key="_btn_salir", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        rol = st.session_state.get("_auth_rol", "")
        st.caption(f"🔑 {'Administrador' if rol == 'admin' else 'Colaborador'}")
        st.caption("☁️ Nube conectada" if nube.nube_activa()
                   else "⚠️ Sin nube: los cambios se pierden al reiniciar")
        st.divider()


def rol_actual() -> str:
    return str(st.session_state.get("_auth_rol", "colaborador"))


def usuario_actual() -> str:
    return str(st.session_state.get("_auth_user", "desconocido"))


def es_admin() -> bool:
    return rol_actual() == "admin"


def encabezado_carga(titulo: str, estado: str, resumen: str,
                     ultima: str | None, ayuda: str) -> None:
    """
    ESTÁNDAR ÚNICO de los módulos de carga: siempre el mismo orden y las
    mismas palabras. Título → estado + resumen → 🕓 última carga → ayuda.
    Había seis formas distintas de decir lo mismo en la otra app.
    """
    st.markdown(f"#### {titulo}")
    st.markdown(f"{estado} {resumen}")
    st.caption(f"🕓 Última actualización: {sello_legible(ultima)}")
    with st.expander("¿Cómo funciona?"):
        st.markdown(ayuda)
