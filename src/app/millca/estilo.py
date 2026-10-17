"""
app/millca/estilo.py
====================
La piel de la demo Millca. Es deliberadamente DISTINTA a la de IA-SBC:
las directivas tienen que ver SU app, no la de la Sociedad Bíblica con
otro nombre.

LA DIRECCIÓN, en una frase: un refugio de paz en la pantalla. Pastel
cálido, una serif con carácter para la Palabra, mucho aire, nada que
grite. El único acento oscuro es la tinta del texto bíblico, que es lo
que se vino a leer.

Dos decisiones técnicas:
· Los colores de Millca se declaran como variables y se aplican con
  transparencias sobre el fondo del tema, así la demo no se rompe si el
  celular está en modo oscuro. Cuando Millca entregue su paleta oficial,
  se cambian seis valores acá y nada más.
· La barra inferior se fuerza a UNA fila igual que en la app principal:
  Streamlit apila las columnas en pantallas angostas.
"""
from __future__ import annotations

import streamlit as st

# ── Paleta provisional "pastel cálido" ───────────────────────────────
# Se reemplaza por la paleta oficial de Millca cuando la entreguen.
ROSA = "#d98a9a"        # acento principal
ROSA_SUAVE = "#f3dfe3"  # fondos de tarjeta
ARENA = "#f6efe6"       # fondo de la lectura
DORADO = "#c9a66b"      # detalles (número de versículo, racha)
TINTA = "#3b2f33"       # texto sobre fondos claros

_ALTO_BARRA = 64

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400&family=Nunito:wght@400;600;700&display=swap');

.block-container {{
  padding-top: 2.4rem;
  padding-bottom: calc({_ALTO_BARRA}px + env(safe-area-inset-bottom, 0px) + 1.2rem);
  max-width: 560px;
  font-family: 'Nunito', system-ui, sans-serif;
}}
#MainMenu, footer, header [data-testid="stStatusWidget"] {{ visibility: hidden; }}
[data-testid="stAppDeployButton"], [data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stSidebar"] {{ display: none; }}

/* La etiqueta de demo: pequeña, arriba, siempre visible. Nadie debe
   creer que esto ya es la app publicada. */
.ml-demo {{
  position: fixed; top: calc(0.45rem + env(safe-area-inset-top, 0px)); right: 0.8rem;
  z-index: 101; font-size: 0.66rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: {ROSA}; border: 1px solid {ROSA}66; border-radius: 999px; padding: 0.15rem 0.6rem;
  background: {ROSA_SUAVE}cc;
}}

/* Encabezado de cada pantalla */
.ml-tope {{ margin: 0.2rem 0 1.1rem; }}
.ml-tope .marca {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: {ROSA}; font-weight: 700; }}
.ml-tope .t {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.9rem;
  font-weight: 500; line-height: 1.1; margin-top: 0.15rem; }}
.ml-tope .s {{ font-size: 0.86rem; opacity: 0.65; margin-top: 0.2rem; }}

/* Tarjeta del versículo del día */
.ml-tarjeta {{
  background: {ROSA_SUAVE}; color: {TINTA}; border-radius: 22px; padding: 1.2rem 1.25rem;
  margin: 0 0 1rem;
}}
.ml-tarjeta .et {{ font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase;
  color: {ROSA}; font-weight: 700; }}
.ml-tarjeta .tx {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.28rem;
  line-height: 1.45; margin: 0.45rem 0 0.4rem; }}
.ml-tarjeta .ref {{ font-size: 0.8rem; color: {DORADO}; font-weight: 700; }}

/* La lectura: fondo arena, serif grande, números en dorado */
.ml-lectura {{
  background: {ARENA}; color: {TINTA}; border-radius: 22px; padding: 1.3rem 1.3rem 1.1rem;
  font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.22rem; line-height: 1.7;
}}
.ml-lectura h3 {{ font-family: inherit; font-weight: 500; font-size: 1.55rem;
  margin: 0 0 0.7rem; color: {TINTA}; }}
.ml-lectura p {{ margin: 0 0 0.55rem; }}
.ml-lectura .v {{ font-family: 'Nunito', sans-serif; font-size: 0.62rem; vertical-align: super;
  color: {DORADO}; font-weight: 700; margin-right: 0.25rem; }}

/* Perfil */
.ml-perfil {{ display: flex; align-items: center; gap: 0.9rem; margin: 0.2rem 0 1rem; }}
.ml-avatar {{
  width: 62px; height: 62px; border-radius: 50%; background: {ROSA_SUAVE};
  color: {ROSA}; display: flex; align-items: center; justify-content: center;
  font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.7rem; font-weight: 500;
  flex: none;
}}
.ml-perfil .n {{ font-size: 1.15rem; font-weight: 700; }}
.ml-perfil .c {{ font-size: 0.82rem; opacity: 0.65; }}
.ml-cifras {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; margin-bottom: 1rem; }}
.ml-cifras div {{ background: {ROSA_SUAVE}; color: {TINTA}; border-radius: 16px; padding: 0.75rem 0.5rem;
  text-align: center; }}
.ml-cifras b {{ display: block; font-size: 1.35rem; color: {ROSA}; }}
.ml-cifras span {{ font-size: 0.7rem; opacity: 0.75; }}
.ml-fila {{ display: flex; justify-content: space-between; padding: 0.7rem 0.2rem;
  border-bottom: 1px solid rgba(128,128,128,0.18); font-size: 0.92rem; }}
.ml-fila span:last-child {{ opacity: 0.55; }}

/* Pestañas (Reels / Videos): Streamlit las pinta rojas por defecto. */
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color: {ROSA} !important; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {ROSA} !important; }}
[data-testid="stTabs"] button {{ font-family: 'Nunito', sans-serif; font-weight: 700; }}

/* Videos */
.ml-video {{ border-radius: 18px; overflow: hidden; margin-bottom: 0.4rem;
  border: 1px solid rgba(128,128,128,0.18); }}
.ml-video-t {{ font-weight: 700; font-size: 0.95rem; margin: 0.3rem 0 0.95rem; }}
.ml-aviso {{ font-size: 0.76rem; opacity: 0.6; margin: -0.3rem 0 1rem; }}

/* Barra inferior: una fila, siempre */
.st-key-ml_barra {{
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 100;
  background: canvas;
  border-top: 1px solid rgba(128,128,128,0.18);
  padding: 0.3rem 0.3rem calc(0.3rem + env(safe-area-inset-bottom, 0px));
}}
.st-key-ml_barra [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important; flex-wrap: nowrap !important; gap: 0 !important;
}}
.st-key-ml_barra [data-testid="stColumn"] {{ flex: 1 1 0 !important; width: auto !important;
  min-width: 0 !important; }}
.st-key-ml_barra .stButton > button {{
  width: 100%; border: none; background: transparent; color: inherit; opacity: 0.5;
  font-size: 0.78rem; font-weight: 700; padding: 0.5rem 0.1rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}}
.st-key-ml_barra .stButton > button:hover {{ background: transparent; opacity: 0.85; }}
.st-key-ml_barra .stButton > button[kind="primary"] {{
  background: transparent; color: {ROSA}; opacity: 1;
  box-shadow: inset 0 2px 0 0 {ROSA};
  border-radius: 0 !important;      /* sin la esquina del botón primario */
}}
.stButton > button[kind="primary"] {{ background: {ROSA}; border-color: {ROSA}; border-radius: 14px; }}

/* El control de letra: Streamlit lo pinta rojo por defecto. La pista
   rellena y la perilla son divs sin atributo propio, anidados a tres
   niveles dentro de stSlider; se tiñen por esa cadena. */
[data-testid="stSlider"] div[style*="position: absolute"] {{ background-color: {ROSA} !important; }}
[data-testid="stSlider"] div[data-baseweb="slider"] > div > div > div {{ background: {ROSA} !important; }}
[data-testid="stSlider"] [role="slider"] {{ background-color: {ROSA} !important; }}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"] {{ color: {ROSA} !important; }}
[data-testid="stSlider"] [data-testid="stSliderTickBarMin"],
[data-testid="stSlider"] [data-testid="stSliderTickBarMax"] {{ display: none; }}
</style>
"""


def aplicar() -> None:
    """Inyecta el CSS de la demo y la etiqueta 'Demo'."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="ml-demo">Demo</div>', unsafe_allow_html=True)


def tope(marca: str, titulo: str, subtitulo: str = "") -> None:
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(f'<div class="ml-tope"><div class="marca">{marca}</div>'
                f'<div class="t">{titulo}</div>{sub}</div>', unsafe_allow_html=True)


def barra(paginas: list, actual_url: str) -> None:
    """Las tres pestañas de la propuesta, fijas abajo y en una fila."""
    with st.container(key="ml_barra"):
        columnas = st.columns(len(paginas))
        for col, pagina in zip(columnas, paginas):
            activa = pagina.url_path == actual_url
            if col.button(pagina.title, key=f"_ml_nav_{pagina.url_path}",
                          type="primary" if activa else "secondary",
                          use_container_width=True) and not activa:
                st.switch_page(pagina)
