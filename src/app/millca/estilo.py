"""
app/millca/estilo.py
====================
La piel de la demo Millca. Es deliberadamente DISTINTA a la de IA-SBC:
las directivas tienen que ver SU app, no la de la Sociedad Bíblica con
otro nombre.

LA DIRECCIÓN, en una frase: un refugio de paz en la pantalla. Pastel
cálido, una serif con carácter para la Palabra, mucho aire, nada que
grite.

DOS DECISIONES QUE NACIERON DE USARLA EN UN CELULAR REAL

1. El distintivo de Streamlit Cloud abajo a la derecha lo pinta LA
   PLATAFORMA, por fuera de la app (en un servidor propio no existe) y
   sus clases cambian con cada versión. Taparlo con CSS es frágil y
   pelearle el rincón es perder: en el celular caía justo encima de la
   tercera pestaña. La barra ahora deja libre esa esquina: ocupa el ancho
   que queda y las tres pestañas se reparten ese espacio. Cuando la app
   sea nativa, ese distintivo no existirá.

2. El modo claro/oscuro NO lo maneja Streamlit: su menú está oculto y
   cambiar ahí el tema afectaría toda la app de la SBC. La demo tiene
   dos paletas propias y la elección vive en la sesión. Toda la pantalla
   se pinta con la paleta elegida, incluido el fondo de la app, así el
   cambio es completo y no "unas tarjetas oscuras sobre fondo blanco".

La barra inferior se fuerza a UNA fila igual que en la app principal:
Streamlit apila las columnas en pantallas angostas.
"""
from __future__ import annotations

import streamlit as st

# ── Paletas ──────────────────────────────────────────────────────────
# La clara es la provisional "pastel cálido"; la oscura es la misma
# familia bajada de luz, con el rosa un poco más vivo para que destaque
# sobre fondo oscuro sin cambiar de identidad. Cuando Millca entregue su
# paleta oficial, se cambian estos valores y nada más.
PALETAS = {
    "claro": {
        "nombre": "Claro",
        "fondo": "#fbf8f5",        # fondo de toda la app
        "texto": "#3b2f33",        # texto general
        "texto_suave": "#7a6c70",
        "rosa": "#d98a9a",         # acento principal
        "rosa_suave": "#f3dfe3",   # fondos de tarjeta
        "arena": "#f6efe6",        # fondo de la lectura
        "dorado": "#c9a66b",       # números de versículo, racha
        "tinta": "#3b2f33",        # texto sobre tarjetas
        "borde": "rgba(90, 60, 70, 0.14)",
        "campo": "#f1ebe6",        # fondo de selectores y cajas
    },
    "oscuro": {
        "nombre": "Oscuro",
        "fondo": "#1b1618",
        "texto": "#efe6e8",
        "texto_suave": "#b4a3a8",
        "rosa": "#e8a2b1",
        "rosa_suave": "#2d2225",
        "arena": "#26201e",
        "dorado": "#d9b77a",
        "tinta": "#efe6e8",
        "borde": "rgba(255, 230, 235, 0.14)",
        "campo": "#2a2325",
    },
}
TEMA_DEFECTO = "claro"


PARAM_TEMA = "tema"   # ?tema=oscuro en la URL


def tema_actual() -> str:
    """
    El tema elegido. Se lee PRIMERO de la URL (?tema=oscuro) y después de
    la sesión.

    POR QUÉ LA URL: la sesión de Streamlit se renueva al refrescar o al
    escribir una dirección, y con ella se perdía la elección: el modo
    oscuro duraba hasta el primer refresco. En la URL sobrevive al
    refresco, a cambiar de pestaña y a compartir el enlace: si Alberto
    les manda …/millca?tema=oscuro, lo abren ya en oscuro.
    """
    try:
        de_url = str(st.query_params.get(PARAM_TEMA, "") or "").strip().lower()
    except Exception:
        de_url = ""
    if de_url in PALETAS:
        st.session_state["_ml_tema"] = de_url
        return de_url
    t = st.session_state.get("_ml_tema", TEMA_DEFECTO)
    t = t if t in PALETAS else TEMA_DEFECTO
    # Tras switch_page la URL llega sin ?tema=: se repone desde la sesión
    # para que un refresco en esta pestaña no vuelva al claro.
    if t != TEMA_DEFECTO:
        try:
            st.query_params[PARAM_TEMA] = t
        except Exception:
            pass
    return t


def fijar_tema(nombre: str) -> None:
    """Guarda la elección en la sesión Y en la URL (ver tema_actual)."""
    if nombre not in PALETAS:
        return
    st.session_state["_ml_tema"] = nombre
    try:
        if nombre == TEMA_DEFECTO:
            st.query_params.pop(PARAM_TEMA, None)   # la URL limpia = claro
        else:
            st.query_params[PARAM_TEMA] = nombre
    except Exception:
        pass


def paleta() -> dict:
    return PALETAS[tema_actual()]


# ── Medidas ──────────────────────────────────────────────────────────
_ALTO_BARRA = 60
# Ancho que se le deja al distintivo de Streamlit Cloud en la esquina
# inferior derecha. Medido en un iPhone: el distintivo ocupa ~110 px de
# ancho con su margen. Si Streamlit lo cambia, se ajusta acá.
_RESERVA_BADGE = 118


def _css(p: dict) -> str:
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400&family=Nunito:wght@400;600;700&display=swap');

/* ── Toda la app toma la paleta elegida ──────────────────────────── */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
  background: {p["fondo"]} !important;
  color: {p["texto"]};
}}
.stApp *:not(svg):not(path) {{ color: inherit; }}
.block-container {{
  padding-top: 2.4rem;
  padding-bottom: calc({_ALTO_BARRA}px + env(safe-area-inset-bottom, 0px) + 1.4rem);
  max-width: 560px;
  font-family: 'Nunito', system-ui, sans-serif;
  color: {p["texto"]};
}}
#MainMenu, footer, header [data-testid="stStatusWidget"] {{ visibility: hidden; }}
[data-testid="stAppDeployButton"], [data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stSidebar"] {{ display: none; }}

/* Campos de formulario con la paleta. BaseWeb pinta el fondo claro en un
   div sin atributo propio (clase emotion), así que se cubre TODO lo que
   cuelga del contenedor de Streamlit, que sí se puede nombrar. */
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stSelectbox"] div[role="group"], [data-testid="stSelectbox"] div[role="group"] *,
[data-testid="stTextInput"] [data-baseweb="input"] *,
[data-testid="stTextArea"] [data-baseweb="textarea"] *,
[data-testid="stNumberInput"] [data-baseweb="input"] * {{
  background-color: {p["campo"]} !important; color: {p["texto"]} !important;
  border-color: {p["borde"]} !important;
}}
/* La caja blanca del selectbox es un div[role="group"] HERMANO de
   [data-baseweb="select"], no hijo: por eso la regla de arriba sola no
   la alcanzaba. Se descubrió preguntándole al navegador, no leyendo. */
[data-testid="stSelectbox"] [data-baseweb="select"] svg {{ fill: {p["texto_suave"]} !important; }}
[data-testid="stExpander"] details {{ background: {p["campo"]} !important;
  border-color: {p["borde"]} !important; }}
[data-baseweb="popover"] li, [data-baseweb="menu"] {{ background: {p["campo"]} !important; color: {p["texto"]} !important; }}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {{ color: {p["texto"]} !important; }}
.stCaption, [data-testid="stCaptionContainer"] p {{ color: {p["texto_suave"]} !important; }}
.stButton > button[kind="secondary"] {{
  background: {p["campo"]}; color: {p["texto"]}; border: 1px solid {p["borde"]}; border-radius: 14px;
}}
.stButton > button[kind="primary"] {{ background: {p["rosa"]}; border-color: {p["rosa"]};
  border-radius: 14px; color: #fff !important; }}
.stButton > button[kind="primary"] p {{ color: #fff !important; }}
a[data-testid="stBaseLinkButton-secondary"] {{ background: {p["campo"]}; color: {p["texto"]} !important;
  border: 1px solid {p["borde"]}; border-radius: 14px; }}
a[data-testid="stBaseLinkButton-primary"] {{ background: {p["rosa"]}; border-color: {p["rosa"]};
  color: #fff !important; border-radius: 14px; }}

/* Etiqueta de demo: pequeña, arriba, siempre visible. */
.ml-demo {{
  position: fixed; top: calc(0.45rem + env(safe-area-inset-top, 0px)); right: 0.8rem;
  z-index: 999991; font-size: 0.66rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: {p["rosa"]} !important; border: 1px solid {p["rosa"]}66; border-radius: 999px;
  padding: 0.15rem 0.6rem; background: {p["fondo"]};
}}

/* Encabezado de cada pantalla */
.ml-tope {{ margin: 0.2rem 0 1.1rem; }}
.ml-tope .marca {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: {p["rosa"]} !important; font-weight: 700; }}
.ml-tope .t {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.9rem;
  font-weight: 500; line-height: 1.1; margin-top: 0.15rem; }}
.ml-tope .s {{ font-size: 0.86rem; color: {p["texto_suave"]} !important; margin-top: 0.2rem; }}

/* Tarjeta del versículo del día */
.ml-tarjeta {{ background: {p["rosa_suave"]}; color: {p["tinta"]}; border-radius: 22px;
  padding: 1.2rem 1.25rem; margin: 0 0 1rem; }}
.ml-tarjeta .et {{ font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase;
  color: {p["rosa"]} !important; font-weight: 700; }}
.ml-tarjeta .tx {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.28rem;
  line-height: 1.45; margin: 0.45rem 0 0.4rem; }}
.ml-tarjeta .ref {{ font-size: 0.8rem; color: {p["dorado"]} !important; font-weight: 700; }}

/* La lectura */
.ml-lectura {{ background: {p["arena"]}; color: {p["tinta"]}; border-radius: 22px;
  padding: 1.3rem 1.3rem 1.1rem; font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.22rem; line-height: 1.7; }}
.ml-lectura h3 {{ font-family: inherit; font-weight: 500; font-size: 1.55rem; margin: 0 0 0.7rem; }}
.ml-lectura p {{ margin: 0 0 0.55rem; }}
.ml-lectura .v {{ font-family: 'Nunito', sans-serif; font-size: 0.62rem; vertical-align: super;
  color: {p["dorado"]} !important; font-weight: 700; margin-right: 0.25rem; }}

/* Perfil */
.ml-perfil {{ display: flex; align-items: center; gap: 0.9rem; margin: 0.2rem 0 1rem; }}
.ml-avatar {{ width: 62px; height: 62px; border-radius: 50%; background: {p["rosa_suave"]};
  color: {p["rosa"]} !important; display: flex; align-items: center; justify-content: center;
  font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.7rem; font-weight: 500; flex: none; }}
.ml-perfil .n {{ font-size: 1.15rem; font-weight: 700; }}
.ml-perfil .c {{ font-size: 0.82rem; color: {p["texto_suave"]} !important; }}
.ml-cifras {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; margin-bottom: 1rem; }}
.ml-cifras div {{ background: {p["rosa_suave"]}; color: {p["tinta"]}; border-radius: 16px;
  padding: 0.75rem 0.5rem; text-align: center; }}
.ml-cifras b {{ display: block; font-size: 1.35rem; color: {p["rosa"]} !important; }}
.ml-cifras span {{ font-size: 0.7rem; color: {p["texto_suave"]} !important; }}
.ml-fila {{ display: flex; justify-content: space-between; padding: 0.7rem 0.2rem;
  border-bottom: 1px solid {p["borde"]}; font-size: 0.92rem; }}
.ml-fila span:last-child {{ color: {p["texto_suave"]} !important; }}

/* Selector de tema: dos pastillas LADO A LADO (Streamlit las apilaría) */
.st-key-ml_tema [data-testid="stHorizontalBlock"],
.st-key-ml_letra [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important; flex-wrap: nowrap !important; gap: 0.6rem !important;
}}
.st-key-ml_tema [data-testid="stColumn"], .st-key-ml_letra [data-testid="stColumn"] {{
  flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }}
.st-key-ml_letra {{ margin: 0.2rem 0 0.9rem; }}
.ml-tema-et {{ font-size: 0.78rem; letter-spacing: 0.1em; text-transform: uppercase;
  color: {p["texto_suave"]} !important; margin: 0.4rem 0 0.4rem; font-weight: 700; }}

/* Videos y pestañas */
.ml-video-t {{ font-weight: 700; font-size: 0.95rem; margin: 0.3rem 0 0.95rem; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color: {p["rosa"]} !important; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {p["rosa"]} !important; }}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background-color: {p["borde"]}; }}
[data-testid="stTabs"] button p {{ font-family: 'Nunito', sans-serif; font-weight: 700; }}

/* ── Barra inferior: una fila, y deja libre la esquina del distintivo ── */
.st-key-ml_barra {{
  position: fixed; left: 0; bottom: 0; z-index: 100;
  right: {_RESERVA_BADGE}px;                 /* la esquina es del distintivo */
  width: auto !important;                    /* Streamlit pone width:100% y, con
                                                left+right+width definidos, el
                                                ancho gana y el right se ignora */
  background: {p["fondo"]};
  padding: 0.25rem 0.2rem calc(0.25rem + env(safe-area-inset-bottom, 0px));
}}
/* La línea de arriba cruza TODA la pantalla aunque la barra pare antes:
   si parara con ella, se vería como un borde sin terminar. */
.st-key-ml_barra::before {{
  content: ""; position: absolute; top: 0; left: 0; height: 1px;
  width: 100vw; background: {p["borde"]};
}}
.st-key-ml_barra [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important; flex-wrap: nowrap !important; gap: 0 !important;
}}
.st-key-ml_barra [data-testid="stColumn"] {{ flex: 1 1 0 !important; width: auto !important;
  min-width: 0 !important; }}
.st-key-ml_barra .stButton > button {{
  width: 100%; border: none; background: transparent; color: {p["texto_suave"]} !important;
  font-size: 0.76rem; font-weight: 700; padding: 0.5rem 0.05rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; border-radius: 0 !important;
}}
.st-key-ml_barra .stButton > button p {{ color: inherit !important; }}
.st-key-ml_barra .stButton > button:hover {{ background: transparent; }}
.st-key-ml_barra .stButton > button[kind="primary"] {{
  background: transparent; color: {p["rosa"]} !important;
  box-shadow: inset 0 2px 0 0 {p["rosa"]}; border-radius: 0 !important;
}}
</style>
"""


def aplicar() -> None:
    """Inyecta el CSS de la paleta elegida y la etiqueta 'Demo'."""
    st.markdown(_css(paleta()), unsafe_allow_html=True)
    st.markdown('<div class="ml-demo">Demo</div>', unsafe_allow_html=True)


def tope(marca: str, titulo: str, subtitulo: str = "") -> None:
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(f'<div class="ml-tope"><div class="marca">{marca}</div>'
                f'<div class="t">{titulo}</div>{sub}</div>', unsafe_allow_html=True)


def barra(paginas: list, actual_url: str) -> None:
    """Las tres pestañas de la propuesta, fijas abajo y en una fila."""
    with st.container(key="ml_barra"):
        columnas = st.columns(len(paginas))
        tema = tema_actual()
        for col, pagina in zip(columnas, paginas):
            activa = pagina.url_path == actual_url
            if col.button(pagina.title, key=f"_ml_nav_{pagina.url_path}",
                          type="primary" if activa else "secondary",
                          use_container_width=True) and not activa:
                # switch_page descarta los parámetros de la URL: el tema
                # queda en la sesión y tema_actual() lo repone al llegar.
                st.session_state["_ml_tema"] = tema
                st.switch_page(pagina)


def selector_tema() -> None:
    """
    Claro / Oscuro como dos botones. El activo va en primario. Al tocar,
    se guarda en la sesión y la página se vuelve a pintar entera con la
    paleta nueva: no hay nada a medias.
    """
    st.markdown('<div class="ml-tema-et">Apariencia</div>', unsafe_allow_html=True)
    actual = tema_actual()
    with st.container(key="ml_tema"):
        columnas = st.columns(len(PALETAS))
        for col, (clave, pal) in zip(columnas, PALETAS.items()):
            if col.button(pal["nombre"], key=f"_ml_tema_{clave}",
                          type="primary" if clave == actual else "secondary",
                          use_container_width=True) and clave != actual:
                fijar_tema(clave)
                st.rerun()
