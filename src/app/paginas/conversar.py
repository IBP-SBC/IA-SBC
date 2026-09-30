"""
paginas/conversar.py
====================
La pantalla de preguntar. Es lo primero que ve quien abre la app.

QUÉ PUEDE CONSULTAR, Y POR QUÉ IMPORTA: sin sesión de administrador, la
búsqueda queda limitada al corpus PÚBLICO (temas bíblicos, fe, vida
cristiana). Los documentos internos —planes, presupuestos, estrategia—
no se tocan ni por accidente: el filtro se aplica en el motor de
búsqueda, no en la pantalla (ver nucleo/indice.buscar).

El administrador conectado ve un interruptor para consultar también lo
interno, porque para eso entró.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin
from app.ui import bloque_fuentes, tope
from nucleo import indice
from nucleo.config import TOP_K_DEFECTO
from nucleo.indice import AMBITO_PUBLICO
from nucleo.modelo import estado as estado_modelo, responder_streaming
from nucleo.util import recortar

tope("Conversar", "Preguntá sobre la Biblia y la fe")

# ── Alcance de la búsqueda ───────────────────────────────────────────
ambito = AMBITO_PUBLICO
if es_admin():
    if st.toggle("Incluir documentos internos", key="_conv_interno",
                 help="Planes, informes y estrategia. Solo vos ves esto."):
        ambito = None          # sin filtro: todo el corpus

disponibles = (indice.documentos_del_ambito(AMBITO_PUBLICO)
               if ambito else sorted(indice.leer_registro()))

if not disponibles:
    st.info(
        "Todavía no hay material cargado para responder.\n\n"
        + ("Entrá a **Administrar → Documentos** y subí los primeros, "
           "marcándolos como públicos." if es_admin() else
           "Estamos preparando el contenido. Mientras tanto, podés leer la "
           "Biblia o armar tu pedido personalizado en los botones de abajo.")
    )
    st.stop()

_listo, _msg = estado_modelo()
if not _listo and es_admin():
    st.warning(_msg)

# ── Historial ────────────────────────────────────────────────────────
if "_chat" not in st.session_state:
    st.session_state["_chat"] = []

AVATARES = {"user": "🙋", "assistant": "📖"}

EJEMPLOS = [
    "¿Qué dice la Biblia sobre la ansiedad?",
    "¿Por dónde empiezo a leer la Biblia?",
    "¿Qué significa la gracia?",
]

if not st.session_state["_chat"]:
    st.caption("Podés empezar por acá:")
    for i, ej in enumerate(EJEMPLOS):
        if st.button(ej, key=f"_conv_ej_{i}", use_container_width=True):
            st.session_state["_pendiente"] = ej
            st.rerun()

for turno in st.session_state["_chat"]:
    with st.chat_message(turno["role"], avatar=AVATARES.get(turno["role"])):
        st.markdown(turno["content"])
        bloque_fuentes(turno.get("fuentes") or [])

# ── Turno nuevo ──────────────────────────────────────────────────────
pregunta = st.chat_input("Escribí tu pregunta…") or st.session_state.pop(
    "_pendiente", None)

if pregunta:
    st.session_state["_chat"].append({"role": "user", "content": pregunta})
    with st.chat_message("user", avatar=AVATARES["user"]):
        st.markdown(pregunta)

    with st.chat_message("assistant", avatar=AVATARES["assistant"]):
        with st.spinner("Buscando…"):
            encontrados = indice.buscar(pregunta, k=TOP_K_DEFECTO,
                                        ambito=ambito)
        if encontrados.empty:
            st.warning("No encontré nada sobre eso en el material disponible. "
                       "Probá con otras palabras.")

        historial = [t for t in st.session_state["_chat"][:-1]
                     if t["role"] in ("user", "assistant")]
        diagnostico: dict = {}
        respuesta = st.write_stream(
            responder_streaming(pregunta, historial, encontrados, None,
                                diagnostico))

        fuentes = []
        if not encontrados.empty:
            for _, fila in encontrados.iterrows():
                ubi = str(fila.get("ubicacion", "") or "").strip()
                fuentes.append({
                    "etiqueta": f"{fila['documento']}" + (f" · {ubi}" if ubi else ""),
                    "extracto": recortar(fila["texto"], 200)})
            bloque_fuentes(fuentes)

        if es_admin() and diagnostico:
            with st.expander("Detalle de esta respuesta"):
                st.markdown(
                    f"- Modelo: `{diagnostico.get('modelo', '—')}`\n"
                    f"- Intentos: {diagnostico.get('intentos', '—')} · "
                    f"fin: `{diagnostico.get('motivo_fin', '—')}`\n"
                    f"- Enviado: {diagnostico.get('caracteres_enviados', 0)} "
                    f"· recibido: {diagnostico.get('caracteres_recibidos', 0)}\n"
                    f"- Duración: {diagnostico.get('segundos', '—')} s")

    # Un turno vacío no se guarda: dejaría dos mensajes del mismo rol
    # seguidos y el proveedor puede rechazar la conversación entera.
    if str(respuesta).strip():
        st.session_state["_chat"].append(
            {"role": "assistant", "content": respuesta, "fuentes": fuentes})
    else:
        st.session_state["_chat"].pop()

if st.session_state["_chat"]:
    if st.button("Empezar de nuevo", key="_conv_limpiar",
                 use_container_width=True):
        st.session_state["_chat"] = []
        st.rerun()
