"""
millca/altar.py · Botón 3 · «Mi Altar Digital»
==============================================
El rincón personal: nombre, foto, constancia de lectura, favoritos y la
relación con la marca. Es el "perfil básico" del Nivel 1.

HONESTIDAD DE LA DEMO: las cifras de racha y capítulos leídos son
ILUSTRATIVAS y se declaran como tales en pantalla. Inventar un hábito que
nadie ha tenido para que se vea bonito sería engañar a quien decide.
"""
from __future__ import annotations

import streamlit as st

from app.millca.estilo import selector_tema, tope
from nucleo import millca

params = millca.leer_parametros()
tope(params["nombre_app"], "Mi Altar Digital", "Tu espacio personal")

nombre = st.session_state.get("_ml_nombre") or params["nombre_usuaria"]
inicial = (nombre.strip()[:1] or "M").upper()

st.markdown(
    f'<div class="ml-perfil"><div class="ml-avatar">{inicial}</div>'
    f'<div><div class="n">{nombre}</div><div class="c">{params["ciudad"]}</div></div></div>',
    unsafe_allow_html=True)

notas_reales = sum(1 for v in st.session_state.get("_ml_notas", {}).values() if v.strip())
st.markdown(
    f'<div class="ml-cifras">'
    f'<div><b>{params["racha_dias"]}</b><span>días seguidos</span></div>'
    f'<div><b>{params["capitulos_leidos"]}</b><span>capítulos leídos</span></div>'
    f'<div><b>{notas_reales or params["notas_guardadas"]}</b><span>notas</span></div>'
    f'</div>', unsafe_allow_html=True)
st.caption("Cifras ilustrativas para la demo. En la app real salen del uso de cada usuaria.")

with st.expander("Editar mi perfil"):
    nuevo = st.text_input("Mi nombre", value=nombre, key="_ml_inp_nombre")
    st.file_uploader("Mi foto", type=["jpg", "jpeg", "png"], key="_ml_foto",
                     help="En la demo la foto no se guarda; muestra el flujo.")
    if st.button("Guardar", key="_ml_perfil_guardar", type="primary"):
        st.session_state["_ml_nombre"] = nuevo.strip() or nombre
        st.rerun()

selector_tema()
st.caption("La elección queda en este dispositivo. En la app real se guarda "
           "en el perfil de la usuaria.")

st.markdown("#### Mis favoritos")
st.markdown('<div class="ml-fila"><span>Juan 3:16</span><span>guardado</span></div>'
            '<div class="ml-fila"><span>Juan 14:6</span><span>guardado</span></div>',
            unsafe_allow_html=True)

st.markdown("#### Mi Millca")
perfil = str(params.get("instagram_perfil", "")).strip()
if perfil:
    st.link_button("Millca en Instagram", perfil, use_container_width=True)
st.markdown('<div class="ml-fila"><span>Tienda Millca</span><span>abrir</span></div>'
            '<div class="ml-fila"><span>Recordatorio de lectura</span><span>6:00 a. m.</span></div>'
            '<div class="ml-fila"><span>Tamaño de letra</span><span>mediana</span></div>',
            unsafe_allow_html=True)
st.caption("La tienda abre dentro de la app en una ventana segura (Nivel 1). "
           "Los recordatorios por notificación llegan con el Nivel 2.")
