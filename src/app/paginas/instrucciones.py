"""
paginas/instrucciones.py
========================
Editor de main.md: cómo conversa el asistente. Solo admin.

POR QUÉ está en la app y no solo en el repositorio: la forma de responder
es una decisión de negocio. Si para cambiar el tono o agregar una regla
hay que abrir GitHub y esperar un despliegue, en la práctica no se cambia
nunca.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin, usuario_actual
from app.ui import encabezado
from nucleo.modelo import REGLAS_FIJAS
from nucleo.instrucciones import (
    guardar_instrucciones,
    leer_instrucciones,
    restaurar_por_defecto,
)

if not es_admin():
    st.warning("Esta sección es solo para administradores.")
    st.stop()

encabezado("Instrucciones generales (main.md)",
           "Esto es lo primero que lee el asistente en CADA conversación: "
           "quién es, cómo responde y qué no puede hacer.", "🧭")

actual = leer_instrucciones()

texto = st.text_area(
    "Instrucciones",
    value=actual,
    height=520,
    key="_main_editor",
    label_visibility="collapsed",
)

c1, c2, _ = st.columns([1, 1, 2])
if c1.button("💾 Guardar", type="primary", key="_main_guardar",
             use_container_width=True):
    msg = guardar_instrucciones(texto, usuario_actual())
    (st.error if msg.startswith("No se") or "FALLÓ" in msg else st.success)(msg)

if c2.button("↩️ Restaurar", key="_main_restaurar", use_container_width=True):
    st.info(restaurar_por_defecto(usuario_actual()))
    st.rerun()

st.divider()

with st.expander("🔒 Reglas que van SIEMPRE (no se pueden editar acá)"):
    st.markdown(
        "Estas reglas se agregan automáticamente después de tus "
        "instrucciones. Sostienen la confianza en la herramienta: sin "
        "ellas, el asistente podría responder sin citar o inventar una "
        "cifra que suene bien."
    )
    st.code(REGLAS_FIJAS, language="text")

with st.expander("💡 Cómo escribir buenas instrucciones"):
    st.markdown(
        "- **Empezá por el porqué**: para qué existe el asistente y a quién "
        "sirve. Eso orienta más que veinte reglas sueltas.\n"
        "- **Sé concreto con el formato**: si querés respuestas de tres "
        "párrafos con la fuente al final, pedilo así.\n"
        "- **Decí qué NO hacer**, con ejemplos. Las prohibiciones vagas no "
        "se cumplen.\n"
        "- **Una regla por línea.** Si no la podés leer de un vistazo, el "
        "modelo tampoco la va a priorizar.\n"
        "- Cambiá de a poco y probá en **💬 Conversar** con una pregunta que "
        "ya sepas responder: así ves el efecto real del cambio."
    )
