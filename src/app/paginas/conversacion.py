"""
paginas/conversacion.py
=======================
La pantalla principal: preguntar y recibir una respuesta respaldada en
los documentos de la SBC.

Lo que el usuario ve, además de la respuesta, es CON QUÉ se respondió.
Esa es la diferencia entre una herramienta de trabajo y un chat bonito:
si no puede verificar, no puede decidir.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin, usuario_actual
from nucleo import indice
from nucleo.claude import responder_streaming
from nucleo.config import (
    MODELOS_DISPONIBLES,
    MODELO_DEFECTO,
    TOP_K_DEFECTO,
    TOP_K_MAX,
)
from nucleo.util import recortar, sello_ahora

st.markdown("## 💬 Conversar")
st.caption("Preguntá lo que necesitás decidir. Respondo con los documentos "
           "oficiales de la SBC y te digo de dónde salió cada cosa.")

estado = indice.resumen_estado()

# ── Sin documentos: no se finge que hay de dónde responder ───────────
if estado["documentos"] == 0:
    st.info(
        "Todavía no hay documentos cargados, así que no tengo con qué "
        "responder.\n\n"
        + ("Andá a **📚 Documentos** y subí los primeros archivos "
           "(planes, informes, estudios Patmos)."
           if es_admin() else
           "Pedile al equipo de Planeación Integrada que cargue los "
           "documentos base.")
    )
    st.stop()

# ── Controles ────────────────────────────────────────────────────────
registro = indice.leer_registro()
nombres_docs = sorted(registro.keys())

with st.sidebar:
    st.markdown("#### ⚙️ Cómo quiero la respuesta")
    filtro_docs = st.multiselect(
        "Buscar solo en estos documentos",
        options=nombres_docs,
        default=[],
        key="_conv_filtro_docs",
        help="Vacío = busco en todos. Útil cuando querés una respuesta "
             "basada únicamente en un estudio o un plan.",
    )
    k = st.slider("Fragmentos que reviso", 4, TOP_K_MAX, TOP_K_DEFECTO,
                  key="_conv_k",
                  help="Más fragmentos = respuesta más completa y más lenta.")
    if es_admin():
        modelo = st.selectbox(
            "Modelo", list(MODELOS_DISPONIBLES),
            index=list(MODELOS_DISPONIBLES).index(MODELO_DEFECTO),
            format_func=lambda m: MODELOS_DISPONIBLES[m],
            key="_conv_modelo",
        )
    else:
        modelo = MODELO_DEFECTO
    if st.button("🧹 Nueva conversación", key="_conv_limpiar",
                 use_container_width=True):
        st.session_state["_chat"] = []
        st.rerun()
    st.caption(f"📚 {estado['documentos']} documentos · "
               f"{estado['fragmentos']:,} fragmentos".replace(",", "."))

# ── Historial ────────────────────────────────────────────────────────
if "_chat" not in st.session_state:
    st.session_state["_chat"] = []

if not st.session_state["_chat"]:
    st.markdown("**Por ejemplo, podés preguntarme:**")
    ejemplos = [
        "¿Qué dicen los estudios sobre el segmento S5 y por qué es prioritario?",
        "¿Cuál es la meta de biblias del 2026 y cómo se reparte?",
        "¿Qué recursos tenemos para el momento de Descubrimiento y Conexión?",
    ]
    for i, ej in enumerate(ejemplos):
        st.markdown(f"- {ej}")

for turno in st.session_state["_chat"]:
    with st.chat_message(turno["role"]):
        st.markdown(turno["content"])
        fuentes = turno.get("fuentes") or []
        if fuentes:
            with st.expander(f"📎 Fuentes consultadas ({len(fuentes)})"):
                for f in fuentes:
                    st.markdown(f"- **{f['etiqueta']}** — {f['extracto']}")

# ── Turno nuevo ──────────────────────────────────────────────────────
pregunta = st.chat_input("Escribí tu pregunta…")
if pregunta:
    st.session_state["_chat"].append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        with st.spinner("Buscando en los documentos…"):
            encontrados = indice.buscar(pregunta, k=k,
                                        documentos=filtro_docs or None)
        if encontrados.empty:
            st.warning(
                "No encontré nada relacionado en los documentos cargados. "
                "Puede ser que el tema no esté cubierto, o que valga la pena "
                "preguntarlo con otras palabras (probá con los términos que "
                "usarían los documentos)."
            )
        # El historial se manda SIN el turno nuevo: ese va aparte.
        historial = [t for t in st.session_state["_chat"][:-1]
                     if t["role"] in ("user", "assistant")]
        respuesta = st.write_stream(
            responder_streaming(pregunta, historial, encontrados, modelo)
        )

        fuentes = []
        if not encontrados.empty:
            for _, fila in encontrados.iterrows():
                ubi = str(fila.get("ubicacion", "") or "").strip()
                fuentes.append({
                    "etiqueta": f"{fila['documento']}" + (f" · {ubi}" if ubi else ""),
                    "extracto": recortar(fila["texto"], 180),
                })
            with st.expander(f"📎 Fuentes consultadas ({len(fuentes)})"):
                for f in fuentes:
                    st.markdown(f"- **{f['etiqueta']}** — {f['extracto']}")

    st.session_state["_chat"].append(
        {"role": "assistant", "content": respuesta, "fuentes": fuentes})

# ── Descargar la conversación ────────────────────────────────────────
if st.session_state["_chat"]:
    lineas = [f"# Conversación IA-SBC · {sello_ahora()} · {usuario_actual()}", ""]
    for t in st.session_state["_chat"]:
        quien = "**Pregunta**" if t["role"] == "user" else "**Respuesta**"
        lineas.append(f"{quien}\n\n{t['content']}\n")
        for f in (t.get("fuentes") or []):
            lineas.append(f"> Fuente: {f['etiqueta']}")
        lineas.append("")
    st.download_button(
        "⬇️ Descargar esta conversación (.md)",
        data="\n".join(lineas).encode("utf-8"),
        file_name=f"conversacion_iasbc_{sello_ahora().replace(' ', '_').replace(':', '')}.md",
        mime="text/markdown",
        key="_conv_descargar",
    )
