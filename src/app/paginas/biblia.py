"""
paginas/biblia.py
=================
Leer la Biblia. Una pantalla, un capítulo, nada más.

DECISIONES DE LECTURA
· El texto manda: tipografía serif, línea suelta y números de versículo
  pequeños en el dorado del canto. Todo lo demás (selectores, botones)
  ocupa lo mínimo.
· Se recuerda dónde iba el lector dentro de la sesión: volver de otra
  pestaña y perder el capítulo es la forma más rápida de que alguien deje
  de leer.
· Mientras no haya texto cargado, la pantalla lo dice con todas las
  letras en vez de mostrar un ejemplo. Un versículo de muestra se
  confunde con el real.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin
from app.ui import tope
from nucleo import biblia

tope("Biblia", "Lectura por capítulo")

if not biblia.hay_texto():
    st.info(
        "Todavía no está cargado el texto bíblico.\n\n"
        + ("Entrá a **Administrar → Texto bíblico** para cargarlo desde los "
           "PDF de la SBC." if es_admin() else
           "Estamos preparándolo. Mientras tanto podés preguntar en "
           "**Conversar** o armar tu pedido en **Personalizar**.")
    )
    st.stop()

versiones = biblia.versiones()
pos = st.session_state.setdefault(
    "_lectura", {"version": versiones[0], "libro": None, "capitulo": 1})
if pos["version"] not in versiones:
    pos["version"] = versiones[0]

# ── Selectores: tres controles en una línea, sin etiquetas largas ────
c1, c2, c3 = st.columns([1, 2, 1])
pos["version"] = c1.selectbox("Versión", versiones,
                              index=versiones.index(pos["version"]),
                              key="_bib_version")

libros = biblia.libros(pos["version"])
if pos["libro"] not in libros:
    pos["libro"] = libros[0] if libros else None
pos["libro"] = c2.selectbox("Libro", libros,
                            index=libros.index(pos["libro"]) if pos["libro"] in libros else 0,
                            key="_bib_libro")

capitulos = biblia.capitulos(pos["version"], pos["libro"])
if pos["capitulo"] not in capitulos:
    pos["capitulo"] = capitulos[0] if capitulos else 1
pos["capitulo"] = c3.selectbox("Cap.", capitulos,
                               index=capitulos.index(pos["capitulo"]) if pos["capitulo"] in capitulos else 0,
                               key="_bib_capitulo")

# ── El capítulo ──────────────────────────────────────────────────────
versiculos = biblia.capitulo(pos["version"], pos["libro"], pos["capitulo"])
if versiculos.empty:
    st.warning("Ese capítulo no está en el texto cargado.")
    st.stop()

st.markdown(f"### {pos['libro']} {pos['capitulo']}")
cuerpo = "".join(
    f'<p><span class="v">{int(f["versiculo"])}</span>{f["texto"]}</p>'
    for _, f in versiculos.iterrows())
st.markdown(f'<div class="sbc-lectura">{cuerpo}</div>', unsafe_allow_html=True)

# ── Moverse de capítulo ──────────────────────────────────────────────
indice_actual = capitulos.index(pos["capitulo"])
anterior, siguiente = st.columns(2)
if indice_actual > 0 and anterior.button("← Anterior", key="_bib_ant",
                                         use_container_width=True):
    pos["capitulo"] = capitulos[indice_actual - 1]
    st.rerun()
if indice_actual < len(capitulos) - 1 and siguiente.button(
        "Siguiente →", key="_bib_sig", use_container_width=True):
    pos["capitulo"] = capitulos[indice_actual + 1]
    st.rerun()

# ── Buscar una frase ─────────────────────────────────────────────────
with st.expander("Buscar una frase"):
    consulta = st.text_input("Frase", key="_bib_buscar",
                             placeholder="todo lo puedo",
                             label_visibility="collapsed")
    if consulta:
        hallazgos = biblia.buscar_texto(consulta, pos["version"])
        if hallazgos.empty:
            st.caption("Esa frase no aparece en esta versión.")
        else:
            st.caption(f"{len(hallazgos)} resultado(s)")
            for _, f in hallazgos.iterrows():
                if st.button(f"{biblia.referencia(f)} — {f['texto'][:70]}…",
                             key=f"_bib_h_{f['libro']}_{f['capitulo']}_{f['versiculo']}",
                             use_container_width=True):
                    pos["libro"] = str(f["libro"])
                    pos["capitulo"] = int(f["capitulo"])
                    st.rerun()
