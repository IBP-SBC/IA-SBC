"""
paginas/conversacion.py
=======================
La pantalla principal: preguntar y recibir una respuesta respaldada en
los documentos de la SBC.

Lo que el usuario ve, además de la respuesta, es CON QUÉ se respondió.
Esa es la diferencia entre una herramienta de trabajo y un chat bonito:
si no puede verificar, no puede decidir.

Y cuando algo sale mal, se dice. Un chat que se queda mudo es la peor
forma de fallar: nadie sabe si preguntar otra vez, esperar, o si la app
está rota.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin, usuario_actual
from app.ui import bloque_fuentes, chips, encabezado
from nucleo import indice
from nucleo.config import MODELOS_SUGERIDOS, TOP_K_DEFECTO, TOP_K_MAX
from nucleo.modelo import estado as estado_modelo, responder_streaming
from nucleo.util import recortar, sello_ahora

encabezado("Conversar", "Respondo con los documentos oficiales de la SBC "
                        "y te digo de dónde salió cada cosa.", "💬")

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

registro = indice.leer_registro()
nombres_docs = sorted(registro.keys())

# ── Panel lateral ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### ⚙️ Cómo quiero la respuesta")
    filtro_docs = st.multiselect(
        "Buscar solo en estos documentos",
        options=nombres_docs, default=[], key="_conv_filtro_docs",
        help="Vacío = busco en todos. Útil cuando querés una respuesta "
             "basada únicamente en un estudio o un plan.",
    )
    k = st.slider("Fragmentos que reviso", 4, TOP_K_MAX, TOP_K_DEFECTO,
                  key="_conv_k",
                  help="Más fragmentos = respuesta más completa y más lenta.")

    # El modelo se elige SEGÚN EL PROVEEDOR configurado. Si no es Claude,
    # no hay lista sugerida: manda el que esté activo (inventar nombres
    # de modelo es la vía rápida a un 404).
    modelo = None
    if es_admin():
        from nucleo.modelo import configuracion as _cfg_modelo
        _cfg = _cfg_modelo()
        _sugeridos = MODELOS_SUGERIDOS.get((_cfg or {}).get("proveedor", ""), {})
        if _sugeridos:
            _actual = (_cfg or {}).get("modelo", "")
            _opciones = list(_sugeridos)
            modelo = st.selectbox(
                "Modelo", _opciones,
                index=_opciones.index(_actual) if _actual in _opciones else 0,
                format_func=lambda m: _sugeridos[m], key="_conv_modelo")

    if st.button("🧹 Nueva conversación", key="_conv_limpiar",
                 use_container_width=True):
        st.session_state["_chat"] = []
        st.rerun()

    st.caption(f"📚 {estado['documentos']} documentos · "
               f"{estado['fragmentos']:,} fragmentos".replace(",", "."))

# Sin proveedor la app no falla: avisa y pasa a modo búsqueda.
_listo_modelo, _msg_modelo = estado_modelo()
if not _listo_modelo:
    st.warning(f"🔎 {_msg_modelo}")

# ── Historial ────────────────────────────────────────────────────────
if "_chat" not in st.session_state:
    st.session_state["_chat"] = []

AVATARES = {"user": "🙋", "assistant": "📖"}

# Preguntas de arranque: un chat vacío no dice qué se le puede pedir.
# Son botones, no texto: en el celular escribir cuesta.
EJEMPLOS = [
    "¿Qué es el segmento S5 y por qué es prioritario para la SBC?",
    "¿Cuál es la meta de biblias 2026 y cómo se reparte?",
    "¿Qué recursos tenemos para el momento de Descubrimiento y Conexión?",
    "¿Qué dicen los estudios sobre los jóvenes y la Biblia?",
]

if not st.session_state["_chat"]:
    st.markdown("**Para empezar, tocá una pregunta o escribí la tuya:**")
    for i, ej in enumerate(EJEMPLOS):
        if st.button(ej, key=f"_conv_ej_{i}", use_container_width=True):
            st.session_state["_pendiente"] = ej
            st.rerun()
    st.markdown("")
    st.caption("Documentos disponibles:")
    chips(nombres_docs, limite=8)

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
        with st.spinner("Buscando en los documentos…"):
            encontrados = indice.buscar(pregunta, k=k,
                                        documentos=filtro_docs or None)
        if encontrados.empty:
            st.warning(
                "No encontré nada relacionado en los documentos cargados. "
                "Puede ser que el tema no esté cubierto, o que valga la pena "
                "preguntarlo con las palabras que usarían los documentos."
            )

        historial = [t for t in st.session_state["_chat"][:-1]
                     if t["role"] in ("user", "assistant")]
        diagnostico: dict = {}
        respuesta = st.write_stream(
            responder_streaming(pregunta, historial, encontrados, modelo,
                                diagnostico)
        )

        fuentes = []
        if not encontrados.empty:
            for _, fila in encontrados.iterrows():
                ubi = str(fila.get("ubicacion", "") or "").strip()
                fuentes.append({
                    "etiqueta": f"{fila['documento']}" + (f" · {ubi}" if ubi else ""),
                    "extracto": recortar(fila["texto"], 220),
                })
            bloque_fuentes(fuentes)

        # Detalle técnico de la llamada: solo para admin y plegado. Existe
        # para que "no respondió" tenga una explicación y no una sospecha.
        if es_admin() and diagnostico:
            with st.expander("🔧 Detalle de esta respuesta"):
                st.markdown(
                    f"- Modelo: `{diagnostico.get('modelo', '—')}`\n"
                    f"- Intentos: {diagnostico.get('intentos', '—')} · "
                    f"motivo de fin: `{diagnostico.get('motivo_fin', '—')}`\n"
                    f"- Enviado: {diagnostico.get('caracteres_enviados', 0):,} "
                    f"caracteres · Recibido: "
                    f"{diagnostico.get('caracteres_recibidos', 0):,}\n"
                    f"- Duración: {diagnostico.get('segundos', '—')} s"
                    .replace(",", ".")
                )

    # Un turno vacío no se guarda: dejaría dos mensajes del mismo rol
    # seguidos y el proveedor puede rechazar la conversación entera.
    if str(respuesta).strip():
        st.session_state["_chat"].append(
            {"role": "assistant", "content": respuesta, "fuentes": fuentes})
    else:
        st.session_state["_chat"].pop()      # se descarta también la pregunta

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
        mime="text/markdown", key="_conv_descargar")
