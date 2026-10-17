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
from nucleo import millca

params = millca.leer_parametros()
tope(params["nombre_app"], "La Palabra", "Tu lectura de hoy")

if millca.resumen_corpus()["versiculos"] == 0:
    st.error("No encuentro el texto bíblico de la demo (data/semilla/juan_rv1909.csv).")
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
caps = millca.capitulos()
pos = st.session_state.setdefault("_ml_capitulo", caps[0])
if pos not in caps:
    pos = caps[0]

c1, c2 = st.columns([2, 1])
pos = c1.selectbox("Capítulo de Juan", caps, index=caps.index(pos),
                   key="_ml_sel_cap", format_func=lambda c: f"Juan {c}")
tam = c2.select_slider("Letra", ["A", "A+", "A++"], value="A+", key="_ml_letra")
st.session_state["_ml_capitulo"] = pos

escala = {"A": "1.08rem", "A+": "1.22rem", "A++": "1.42rem"}[tam]
versiculos = millca.capitulo(pos)
cuerpo = "".join(f'<p><span class="v">{int(f["versiculo"])}</span>{f["texto"]}</p>'
                 for _, f in versiculos.iterrows())
st.markdown(f'<div class="ml-lectura" style="font-size:{escala}">'
            f'<h3>Juan {pos}</h3>{cuerpo}</div>', unsafe_allow_html=True)
st.caption("Reina-Valera 1909 · dominio público. En la app real irá la "
           "versión que Millca elija, con su licencia.")

i = caps.index(pos)
a, b = st.columns(2)
if i > 0 and a.button("← Juan " + str(caps[i - 1]), key="_ml_ant",
                      use_container_width=True):
    st.session_state["_ml_capitulo"] = caps[i - 1]
    st.rerun()
if i < len(caps) - 1 and b.button("Juan " + str(caps[i + 1]) + " →",
                                  key="_ml_sig", use_container_width=True):
    st.session_state["_ml_capitulo"] = caps[i + 1]
    st.rerun()

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
