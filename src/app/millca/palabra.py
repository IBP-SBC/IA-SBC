"""
millca/palabra.py · Botón 1 · «La Palabra»
==========================================
Lectura bíblica con diseño descansado, pensada para el devocional diario.

Lo que la demo muestra de la propuesta: el versículo del día al abrir,
el evangelio de Juan completo por capítulos, moverse entre capítulos con
un toque, ajustar el tamaño de letra y el bloc de notas. Las notas se
guardan SOLO en esta sesión del navegador, que es exactamente el
comportamiento del Nivel 1 de la propuesta ("almacenamiento local").
"""
from __future__ import annotations

import streamlit as st

from app.millca.estilo import tope
from app.ui import llevar_a
from nucleo import millca

params = millca.leer_parametros()
tope(params["nombre_app"], "La Palabra", "Tu lectura de hoy")

if millca.resumen_corpus()["versiculos"] == 0:
    st.error("No encuentro el texto bíblico de la demo (data/semilla/nt_rv1909.csv).")
    st.stop()

# ── Versículo del día ────────────────────────────────────────────────
vdd = millca.versiculo_del_dia()
if vdd:
    st.markdown(
        f'<div class="ml-tarjeta"><div class="et">Versículo de hoy</div>'
        f'<div class="tx">{vdd["texto"]}</div>'
        f'<div class="ref">{vdd["referencia"]} · RV1909</div></div>',
        unsafe_allow_html=True)

# ── Capítulo ─────────────────────────────────────────────────────────
# EL SELECTOR ES LA ÚNICA FUENTE DE VERDAD del capítulo (su clave en la
# sesión). Hasta la v2.2.1 los botones Anterior/Siguiente escribían en
# otra variable y el selector, que guarda su propio valor, la pisaba en
# el redibujo: tocar "Juan 2 →" dejaba la página en Juan 1. Ahora los
# botones cambian el valor del selector con una función on_click, que
# Streamlit ejecuta ANTES de redibujar (cambiarlo después de dibujado
# está prohibido y lanza un error).
CLAVE_CAP = "_ml_sel_cap"
caps = millca.capitulos()
if st.session_state.get(CLAVE_CAP) not in caps:
    st.session_state[CLAVE_CAP] = caps[0]


def _ir_a(capitulo: int) -> None:
    st.session_state[CLAVE_CAP] = capitulo


# ¿Cambió el capítulo desde el último dibujo? Si cambió, al final de la
# página se lleva la pantalla al comienzo de la lectura: los botones están
# al final del texto y, sin esto, Juan 2 se abría mostrando su final.
_visto = st.session_state.get("_ml_cap_visto")
cambio_capitulo = _visto is not None and _visto != st.session_state[CLAVE_CAP]
st.session_state["_ml_cap_visto"] = st.session_state[CLAVE_CAP]


pos = st.selectbox("Capítulo de Juan", caps, key=CLAVE_CAP,
                   format_func=lambda c: f"Juan {c}")

# Tamaño de letra como tres botones, igual que Claro/Oscuro: coherente
# con el resto de la demo y fácil de tocar con el pulgar. Antes era un
# deslizador de Streamlit que no aceptaba la paleta (la pista quedaba
# roja) y que en el celular es difícil de acertar.
TAMANOS = {"A": "1.08rem", "A+": "1.22rem", "A++": "1.42rem"}
tam = st.session_state.setdefault("_ml_letra", "A+")
with st.container(key="ml_letra"):
    cols = st.columns(len(TAMANOS))
    for col, nombre in zip(cols, TAMANOS):
        if col.button(nombre, key=f"_ml_letra_{nombre}",
                      type="primary" if nombre == tam else "secondary",
                      use_container_width=True) and nombre != tam:
            st.session_state["_ml_letra"] = nombre
            st.rerun()
escala = TAMANOS[tam]
versiculos = millca.capitulo(pos)
cuerpo = "".join(f'<p><span class="v">{int(f["versiculo"])}</span>{f["texto"]}</p>'
                 for _, f in versiculos.iterrows())
st.markdown(f'<div class="ml-lectura" style="font-size:{escala}">'
            f'<h3>Juan {pos}</h3>{cuerpo}</div>', unsafe_allow_html=True)
st.caption("Reina-Valera 1909 · dominio público. En la app real irá la "
           "versión que Millca elija, con su licencia.")

i = caps.index(pos)
with st.container(key="ml_nav"):          # lado a lado también en el celular
    a, b = st.columns(2)
    if i > 0:
        a.button(f"← Juan {caps[i - 1]}", key="_ml_ant", on_click=_ir_a,
                 args=(caps[i - 1],), use_container_width=True)
    if i < len(caps) - 1:
        b.button(f"Juan {caps[i + 1]} →", key="_ml_sig", on_click=_ir_a,
                 args=(caps[i + 1],), use_container_width=True)

# ── Bloc de notas (almacenamiento local, como el Nivel 1) ────────────
st.markdown("")
with st.expander("Mi diario de lectura"):
    notas = st.session_state.setdefault("_ml_notas", {})
    nota = st.text_area("Lo que me habló hoy", value=notas.get(pos, ""),
                        key=f"_ml_nota_{pos}", height=110,
                        placeholder="Escribí acá tu reflexión de este capítulo…")
    if st.button("Guardar nota", key=f"_ml_guardar_{pos}", type="primary"):
        notas[pos] = nota
        st.success("Guardada en este dispositivo.")
    guardadas = {k: v for k, v in notas.items() if v.strip()}
    if guardadas:
        st.caption(f"{len(guardadas)} nota(s) en este dispositivo. En el Nivel 2 "
                   "se respaldan en la nube y viajan con la usuaria.")

# Al FINAL de la página, para que la lectura ya exista cuando corra.
if cambio_capitulo:
    st.session_state["_ml_saltos"] = st.session_state.get("_ml_saltos", 0) + 1
    llevar_a(".ml-lectura", f"Juan {pos} #{st.session_state['_ml_saltos']}")
