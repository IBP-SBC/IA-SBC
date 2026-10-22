"""
paginas/biblia.py
=================
Leer la Biblia. Una pantalla, un capítulo, nada más.

DECISIONES DE LECTURA
· El texto manda: tipografía serif, línea suelta y números de versículo
  pequeños en el dorado del canto. Selectores y botones ocupan lo mínimo.
· Se lee de corrido: "Siguiente" pasa del último capítulo de un libro al
  primero del siguiente (Mateo 28 → Marcos 1), como en papel.
· Se dice siempre QUÉ texto se está leyendo. Mientras no haya versiones
  oficiales cargadas se muestra el Nuevo Testamento RV1909 de ejemplo, y
  la pantalla lo nombra.

LA REGLA DE ESTADO (nacida de un error propio): libro y capítulo viven
SOLO en las claves de sus selectores. Hasta la v2.2.1 los botones
escribían en otra variable y el selector la pisaba al redibujar: los
botones Anterior/Siguiente nunca funcionaron. Ahora todo cambio entra por
funciones on_click/on_change, que Streamlit ejecuta antes de redibujar.

AL CAMBIAR DE CAPÍTULO la pantalla se lleva al comienzo del capítulo
nuevo (ui.llevar_a). Sin eso, quien tocaba "Siguiente" al final del
texto caía en el FINAL del capítulo siguiente y tenía que subir a mano.
"""
from __future__ import annotations

import streamlit as st

from app.estado import es_admin
from app.ui import llevar_a, tope
from nucleo import biblia

ss = st.session_state
K_VER, K_LIB, K_CAP = "_bib_version", "_bib_libro", "_bib_capitulo"
K_VISTO, K_SALTOS = "_bib_visto", "_bib_saltos"

if not biblia.hay_texto():
    tope("Biblia", "Lectura por capítulo")
    st.info(
        "Todavía no está cargado el texto bíblico.\n\n"
        + ("Entrá a **Configuración → Texto bíblico** para cargarlo." if es_admin()
           else "Estamos preparándolo. Mientras tanto podés preguntar en "
                "**Conversar** o armar tu pedido en **Personalizar**.")
    )
    st.stop()

# ── Estado válido ANTES de dibujar los selectores ────────────────────
versiones = biblia.versiones()
if ss.get(K_VER) not in versiones:
    ss[K_VER] = versiones[0]
libros = biblia.libros(ss[K_VER])
if ss.get(K_LIB) not in libros:
    ss[K_LIB] = libros[0]
capitulos = biblia.capitulos(ss[K_VER], ss[K_LIB])
if ss.get(K_CAP) not in capitulos:
    ss[K_CAP] = capitulos[0]

# ¿Cambió el capítulo desde el último dibujo? (botones, selectores o un
# resultado de búsqueda; las funciones on_click ya corrieron a esta
# altura). En el primer ingreso no hay "antes" y no se mueve nada.
_actual = (ss[K_VER], ss[K_LIB], ss[K_CAP])
cambio_capitulo = ss.get(K_VISTO) not in (None, _actual)
ss[K_VISTO] = _actual


def _al_cambiar_version() -> None:
    libs = biblia.libros(ss[K_VER])
    if ss.get(K_LIB) not in libs:
        ss[K_LIB] = libs[0]
    caps = biblia.capitulos(ss[K_VER], ss[K_LIB])
    if ss.get(K_CAP) not in caps:
        ss[K_CAP] = caps[0]


def _al_cambiar_libro() -> None:
    caps = biblia.capitulos(ss[K_VER], ss[K_LIB])
    ss[K_CAP] = caps[0] if caps else 1


def _ir_a(libro: str, capitulo: int) -> None:
    ss[K_LIB] = libro
    ss[K_CAP] = capitulo


ejemplo = biblia.es_ejemplo()
tope("Biblia", "Reina-Valera 1909 · Nuevo Testamento" if ejemplo
     else "Lectura por capítulo")

if len(versiones) > 1:
    st.selectbox("Versión", versiones, key=K_VER, on_change=_al_cambiar_version)

with st.container(key="fila_bib_sel"):        # lado a lado también en el celular
    c1, c2 = st.columns([3, 1])
    c1.selectbox("Libro", libros, key=K_LIB, on_change=_al_cambiar_libro)
    c2.selectbox("Cap.", capitulos, key=K_CAP)

# ── El capítulo ──────────────────────────────────────────────────────
versiculos = biblia.capitulo(ss[K_VER], ss[K_LIB], ss[K_CAP])
if versiculos.empty:
    st.warning("Ese capítulo no está en el texto cargado.")
    st.stop()

with st.container(key="bib_capitulo"):     # el ancla para llevar_a()
    st.markdown(f"### {ss[K_LIB]} {ss[K_CAP]}")
    cuerpo = "".join(
        f'<p><span class="v">{int(f["versiculo"])}</span>{f["texto"]}</p>'
        for _, f in versiculos.iterrows())
    st.markdown(f'<div class="sbc-lectura">{cuerpo}</div>', unsafe_allow_html=True)

# ── Moverse de capítulo, cruzando libros ─────────────────────────────
anterior, siguiente = biblia.vecinos(ss[K_VER], ss[K_LIB], ss[K_CAP])
with st.container(key="fila_bib_nav"):
    a, b = st.columns(2)
    if anterior:
        a.button(f"← {anterior[0]} {anterior[1]}", key="_bib_ant", on_click=_ir_a,
                 args=anterior, use_container_width=True)
    if siguiente:
        b.button(f"{siguiente[0]} {siguiente[1]} →", key="_bib_sig", on_click=_ir_a,
                 args=siguiente, use_container_width=True)

if ejemplo:
    st.caption("Texto de ejemplo, de dominio público. Las versiones de la SBC "
               "se cargan en Configuración y reemplazan a este.")

# ── Buscar una frase ─────────────────────────────────────────────────
with st.expander("Buscar una frase"):
    consulta = st.text_input("Frase", key="_bib_buscar",
                             placeholder="todo lo puedo",
                             label_visibility="collapsed")
    if consulta:
        hallazgos = biblia.buscar_texto(consulta, ss[K_VER])
        if hallazgos.empty:
            st.caption("Esa frase no aparece en este texto.")
        else:
            st.caption(f"{len(hallazgos)} resultado(s)"
                       + (" · se muestran los primeros 30" if len(hallazgos) >= 30 else ""))
            for i, (_, f) in enumerate(hallazgos.iterrows()):
                st.button(f"{biblia.referencia(f)} — {str(f['texto'])[:70]}…",
                          key=f"_bib_h_{i}", on_click=_ir_a,
                          args=(str(f["libro"]), int(f["capitulo"])),
                          use_container_width=True)

# ── Al cambiar de capítulo, la pantalla va a su comienzo ─────────────
# Al FINAL de la página, para que el ancla ya exista cuando corra.
if cambio_capitulo:
    ss[K_SALTOS] = ss.get(K_SALTOS, 0) + 1
    llevar_a(".st-key-bib_capitulo", f"{ss[K_LIB]} {ss[K_CAP]} #{ss[K_SALTOS]}")
