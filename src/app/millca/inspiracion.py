"""
millca/inspiracion.py · Botón 2 · «Inspiración Diaria»
======================================================
El corazón multimedia: los reels de Millca y videos de YouTube, dentro de
la app. Es el "espejo de redes sociales" del Nivel 1 de la propuesta.

SOBRE INSTAGRAM, dicho sin maquillar: el reproductor incrustado es el
oficial de Instagram y funciona con publicaciones públicas, pero en el
celular Instagram a veces lo reemplaza por una tarjeta que dice "Ver en
Instagram". Eso lo decide Instagram, no la app, y pasa igual en cualquier
app que incruste reels. Por eso cada reel lleva debajo un botón para
abrirlo: si la tarjeta aparece, la demo no se queda trabada.
"""
from __future__ import annotations

import streamlit as st

from app.millca.estilo import tope
from nucleo import millca

params = millca.leer_parametros()
tope(params["nombre_app"], "Inspiración Diaria", "Academia Chica Millca")

videos = [v for v in params.get("videos", []) if str(v.get("url", "")).strip()]
if not videos:
    st.info("Todavía no hay videos configurados. Se agregan en "
            "Configuración → Millca con los enlaces de YouTube o Instagram.")
    st.stop()

clasificados = [(v, millca.clasificar_video(v["url"])) for v in videos]
reels = [(v, i) for v, i in clasificados if i["plataforma"] == "instagram"]
tubes = [(v, i) for v, i in clasificados if i["plataforma"] == "youtube"]
otros = [(v, i) for v, i in clasificados if i["plataforma"] not in ("instagram", "youtube")]


def _reel(v: dict, info: dict) -> None:
    st.markdown(f'<div class="ml-video-t">{v.get("titulo") or "Reel"}</div>',
                unsafe_allow_html=True)
    if info["embed"]:
        # El reproductor tarda un par de segundos en aparecer; mientras,
        # el botón de abajo ya dice qué es esto y a dónde lleva. Nunca un
        # hueco mudo de 600 píxeles.
        st.iframe(info["embed"], height=560)
    st.link_button("Ver en Instagram", info["url"], use_container_width=True)
    st.markdown("")


def _tube(v: dict, info: dict) -> None:
    st.markdown(f'<div class="ml-video-t">{v.get("titulo") or "Video"}</div>',
                unsafe_allow_html=True)
    if info["embed"]:
        st.iframe(info["embed"], height=215)
    else:
        st.link_button("Abrir el video", info["url"], use_container_width=True)
        if info["aviso"]:
            st.caption(info["aviso"])
    st.markdown("")


pestanas = []
if reels:
    pestanas.append("Reels")
if tubes:
    pestanas.append("Videos")
if otros:
    pestanas.append("Más")

for nombre, tab in zip(pestanas, st.tabs(pestanas)):
    with tab:
        if nombre == "Reels":
            for v, i in reels:
                _reel(v, i)
            st.caption("Reels públicos de la cuenta de Millca, dentro de la app. "
                       "Si Instagram muestra una tarjeta en vez del video, el "
                       "botón lo abre.")
        elif nombre == "Videos":
            for v, i in tubes:
                _tube(v, i)
            st.caption("YouTube puede mostrar su propia publicidad: es una "
                       "condición de esa plataforma.")
        else:
            for v, i in otros:
                st.link_button(v.get("titulo") or i["url"], i["url"],
                               use_container_width=True)

perfil = str(params.get("instagram_perfil", "")).strip()
if perfil:
    st.link_button("Seguir a Millca en Instagram", perfil, use_container_width=True)
