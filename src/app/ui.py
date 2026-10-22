"""
app/ui.py
=========
La piel de la app. El objetivo es que se sienta una app de celular: menú
abajo, una cosa por pantalla, poco texto y nada que distraiga.

CUATRO REGLAS

1. **El pulgar manda.** La navegación va abajo, donde llega el dedo sin
   estirar la mano. El acceso de configuración va arriba a la izquierda,
   fuera del camino de quien solo viene a usar la app.
2. **Sin iconos.** Los nombres se leen; los símbolos hay que
   interpretarlos. Y una fila de emojis de colores delata que la pantalla
   la armó una máquina. Texto y silencio.
3. **Funciona en claro y en oscuro.** El tema solo fija el color de
   acento, uno por modo ([theme.light] y [theme.dark] en config.toml);
   nunca [theme] a secas, que forzaría el modo claro para todos. No hay
   colores de fondo fijos. El único acento fuerte es el dorado del canto,
   y solo en la lectura.
4. **Esto dibuja, no calcula.**
"""
from __future__ import annotations

import json

import streamlit as st

from nucleo.config import COLOR_ACENTO, COLOR_PRIMARIO, COLOR_PRIMARIO_OSCURO
from nucleo.util import recortar

# Alto reservado para la barra inferior: el contenido tiene que poder
# terminar sin quedar tapado por ella.
_ALTO_BARRA = 62
# Ancho que se le deja al distintivo de Streamlit Cloud en la esquina
# inferior derecha (lo pinta la plataforma por fuera de la app y no se
# puede ocultar de forma confiable). Misma medida que en la demo Millca,
# verificada en un viewport de iPhone.
_RESERVA_BADGE = 118

_CSS = f"""
<style>
/* ---- Estructura general ---- */
.block-container {{
  padding-top: 2.6rem;
  padding-bottom: calc({_ALTO_BARRA}px + env(safe-area-inset-bottom, 0px) + 1.2rem);
  max-width: 760px;
}}
#MainMenu, footer, header [data-testid="stStatusWidget"] {{ visibility: hidden; }}
[data-testid="stAppDeployButton"], [data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stSidebar"] {{ display: none; }}
h1, h2, h3 {{ letter-spacing: -0.015em; }}

/* ---- Encabezado de pantalla ---- */
.sbc-tope {{ margin: 0 0 1rem 0; }}
.sbc-tope .t {{ font-size: 1.3rem; font-weight: 600; line-height: 1.25; }}
.sbc-tope .s {{ font-size: 0.87rem; opacity: 0.65; margin-top: 0.1rem; }}

/* ---- Acceso de configuracion, arriba a la IZQUIERDA ---- */
/* Va a la misma altura que la cabecera de Streamlit, que mide 2.875rem
   y queda por ENCIMA en el apilado: con z-index más alto que ella
   (999990) el enlace se ve; con menos, la cabecera transparente lo tapa
   aunque exista. Pasó en la v2.1: el botón estaba y nadie lo veía. */
.st-key-acceso_tope {{
  position: fixed;
  top: calc(0.55rem + env(safe-area-inset-top, 0px));
  left: 0.9rem;
  z-index: 999991;
  width: auto;
}}
.st-key-acceso_tope .stButton > button {{
  border: 1px solid rgba(128,128,128,0.35);
  border-radius: 999px;
  background: canvas;
  color: inherit;
  opacity: 0.8;
  font-size: 0.78rem;
  font-weight: 500;
  padding: 0.15rem 0.7rem;
  min-height: 0;
}}
.st-key-acceso_tope .stButton > button:hover {{ opacity: 1; }}

/* ---- Barra inferior ---- */
/* El distintivo "Hosted with Streamlit" lo pinta la PLATAFORMA, por fuera
   de la app, en la esquina inferior derecha. La barra le cede esa esquina
   en vez de pelearla: termina antes del borde y las tres secciones se
   reparten el ancho que queda. width:auto es obligatorio: Streamlit le
   pone width:100% a sus contenedores y, con left+right+width definidos,
   el ancho gana y el right se ignora (pasó en la demo Millca). */
.st-key-barra_inferior {{
  position: fixed;
  left: 0; bottom: 0;
  right: {_RESERVA_BADGE}px;
  width: auto !important;
  z-index: 100;
  background: canvas;
  padding: 0.3rem 0.3rem calc(0.3rem + env(safe-area-inset-bottom, 0px));
}}
/* La línea de arriba cruza toda la pantalla aunque la barra pare antes. */
.st-key-barra_inferior::before {{
  content: ""; position: absolute; top: 0; left: 0; height: 1px;
  width: 100vw; background: rgba(128,128,128,0.22);
}}

/* EL ARREGLO QUE IMPORTA: Streamlit apila las columnas una debajo de
   otra cuando la pantalla es angosta, que es justo el caso del celular.
   Una barra de navegacion en vertical ocupa media pantalla y deja de ser
   una barra. Aca se le fuerza la fila y se reparte el ancho en partes
   iguales, pase lo que pase con el ancho del telefono. */
.st-key-barra_inferior [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 0 !important;
  align-items: stretch;
}}
.st-key-barra_inferior [data-testid="stColumn"] {{
  flex: 1 1 0 !important;
  width: auto !important;
  min-width: 0 !important;
}}
.st-key-barra_inferior .stButton > button {{
  width: 100%;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.5;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.5rem 0.1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.st-key-barra_inferior .stButton > button:hover {{
  background: transparent;
  opacity: 0.8;
}}
.st-key-barra_inferior .stButton > button[kind="primary"] {{
  background: transparent;
  color: {COLOR_PRIMARIO};
  opacity: 1;
  box-shadow: inset 0 2px 0 0 {COLOR_PRIMARIO};
  border-radius: 0 !important;
}}
/* En modo oscuro el azul institucional casi no se ve sobre el fondo
   (contraste 2,18:1): la pestaña activa toma el mismo azul aclarado que
   usa el tema oscuro. Streamlit sigue la preferencia del sistema (su menú
   de tema está oculto), así que esta consulta coincide con su modo. */
@media (prefers-color-scheme: dark) {{
  .st-key-barra_inferior .stButton > button[kind="primary"] {{
    color: {COLOR_PRIMARIO_OSCURO};
    box-shadow: inset 0 2px 0 0 {COLOR_PRIMARIO_OSCURO};
  }}
}}

/* ---- Filas que NO se apilan en el celular ----
   Cualquier contenedor con clave "fila_…" mantiene sus columnas lado a
   lado (Streamlit las apila en pantallas angostas). En la fila de los
   selectores de la Biblia el libro ocupa tres partes y el capítulo una. */
[class*="st-key-fila_"] [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 0.5rem !important;
}}
[class*="st-key-fila_"] [data-testid="stColumn"] {{
  flex: 1 1 0 !important;
  width: auto !important;
  min-width: 0 !important;
}}
.st-key-fila_bib_sel [data-testid="stColumn"]:first-child {{ flex: 3 1 0 !important; }}

/* ---- Chat ---- */
[data-testid="stChatMessage"] {{
  border-radius: 14px;
  padding: 0.55rem 0.85rem;
  margin-bottom: 0.45rem;
  background: rgba(128,128,128,0.07);
}}

/* ---- Lectura biblica: el unico lugar con el acento dorado ---- */
.sbc-lectura {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.06rem;
  line-height: 1.8;
  border-right: 3px solid #a8842c;
  padding-right: 0.9rem;
}}
.sbc-lectura .v {{
  font-size: 0.68rem;
  vertical-align: super;
  color: #a8842c;
  margin-right: 0.22rem;
  font-weight: 600;
}}

/* ---- Piezas sueltas ---- */
.sbc-chip {{
  display: inline-block;
  padding: 0.12rem 0.55rem;
  margin: 0.12rem 0.25rem 0.12rem 0;
  border: 1px solid {COLOR_ACENTO}55;
  background: {COLOR_ACENTO}14;
  border-radius: 999px;
  font-size: 0.76rem;
}}
.sbc-fuente {{
  border-left: 3px solid {COLOR_ACENTO}66;
  padding: 0.12rem 0 0.12rem 0.7rem;
  margin: 0.4rem 0;
  font-size: 0.85rem;
}}
.sbc-fuente span {{ opacity: 0.7; }}
/* Botones principales SIEMPRE en el azul institucional oscuro, también en
   modo oscuro: el tema los pintaría con el acento claro de ese modo y el
   texto blanco encima quedaría con contraste 2,5:1 (con este, 8,7:1).
   Streamlit usa tres tipos distintos: el botón normal, el de enviar un
   formulario (el "Entrar" del acceso salía ROJO porque solo se cubría el
   primero) y el de enlace.
   SIN !important: con él, esta regla le ganaba a la de la barra inferior
   y la pestaña activa quedaba como un bloque azul con el texto azul
   encima, invisible. La especificidad de estos selectores ya basta para
   ganarle al estilo de Streamlit. */
.stButton > button[kind="primary"],
button[kind="primaryFormSubmit"],
a[data-testid="stBaseLinkButton-primary"] {{
  background-color: {COLOR_PRIMARIO};
  border-color: {COLOR_PRIMARIO};
  border-radius: 12px;
}}
/* Etiquetas de lo elegido en un selector múltiple: SIEMPRE el azul
   oscuro. El tema las pintaría con el acento de cada modo, y en modo
   oscuro ese acento es claro: el texto blanco encima quedaría con
   contraste 2,5:1. */
[data-baseweb="tag"],
[data-testid="stMultiSelectTagsContainer"] [data-tag] {{
  background-color: {COLOR_PRIMARIO} !important;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Inyecta el CSS. Se llama una vez, desde Home.py."""
    st.markdown(_CSS, unsafe_allow_html=True)


def tope(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de pantalla: que estoy mirando y para que sirve."""
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(f'<div class="sbc-tope"><div class="t">{titulo}</div>{sub}</div>',
                unsafe_allow_html=True)


def acceso_tope(pagina_admin, hay_sesion: bool, en_admin: bool) -> None:
    """
    El acceso de configuracion, arriba a la izquierda y discreto.

    Esta siempre visible porque es la puerta, no el permiso: esconderlo
    obligaria a saberse una direccion de memoria. Pero no compite con las
    tres secciones de abajo, que son lo que la gente vino a usar.
    """
    if en_admin:
        return
    with st.container(key="acceso_tope"):
        etiqueta = "Configuración" if hay_sesion else "Entrar"
        if st.button(etiqueta, key="_acceso_admin"):
            st.switch_page(pagina_admin)


def barra_inferior(paginas: list, actual_url: str) -> None:
    """
    El menu: un boton por seccion, fijo abajo y SIEMPRE en una fila.

    Solo el nombre, sin icono. Con tres secciones y nombres cortos el
    texto se lee de un vistazo y no hay que descifrar un simbolo.
    """
    with st.container(key="barra_inferior"):
        columnas = st.columns(len(paginas))
        for col, pagina in zip(columnas, paginas):
            activa = pagina.url_path == actual_url
            if col.button(pagina.title, key=f"_nav_{pagina.url_path}",
                          type="primary" if activa else "secondary",
                          use_container_width=True) and not activa:
                st.switch_page(pagina)


# Lo que se deja libre arriba al llevar la pantalla a un punto: la
# cabecera transparente de Streamlit (2.875rem = 46 px) y el botón Entrar
# están fijos ahí y taparían lo que quede justo en el borde.
_MARGEN_SUPERIOR = 56


def llevar_a(ancla_css: str, marca: str) -> None:
    """
    Desplaza la pantalla hasta el elemento `ancla_css`, o arriba del todo
    si no lo encuentra (nunca deja a nadie abajo).

    POR QUÉ: los botones para pasar de capítulo están al FINAL del texto.
    Al tocarlos, Streamlit redibuja pero la pantalla conserva el
    desplazamiento: el capítulo nuevo se abría mostrando su final y había
    que subir a mano en cada capítulo. Streamlit no trae una orden para
    desplazar la pantalla, así que se hace con un script mínimo.

    CÓMO:
    · Se llama SOLO cuando el capítulo cambió (lo decide cada página). En
      el primer ingreso o al escribir en el buscador no se mueve nada.
    · st.html con JavaScript corre el script en la página, y el navegador
      lo vuelve a correr cada vez que su contenido cambia. `marca`
      (capítulo + contador) lo hace distinto en cada cambio.
    · Lo que se desplaza NO es la página sino el contenedor principal de
      Streamlit, y su etiqueta cambia entre versiones (<section> en la
      1.57, <main> en la 1.66). Por eso el script no lo nombra: sube desde
      el ancla hasta el primer contenedor que tenga barra de
      desplazamiento. Si no encuentra el ancla, lleva arriba del todo.
    · Va al FINAL de la página: así el ancla, que está más arriba, ya
      existe cuando el script corre.
    """
    script = (
        "<script>(function () {"
        f"  var marca = {json.dumps(marca)};"   # hace único el bloque
        f"  var ancla = document.querySelector({json.dumps(ancla_css)});"
        "  function contenedor(el) {"
        "    for (var e = el && el.parentElement; e; e = e.parentElement) {"
        "      var oy = getComputedStyle(e).overflowY;"
        "      if ((oy === 'auto' || oy === 'scroll') && e.scrollHeight > e.clientHeight + 1) return e;"
        "    }"
        "    return document.querySelector('[data-testid=\"stMain\"]')"
        "        || document.scrollingElement || document.documentElement;"
        "  }"
        "  requestAnimationFrame(function () {"
        "    var cont = contenedor(ancla);"
        "    var pagina = cont === document.scrollingElement || cont === document.documentElement;"
        "    var arriba = pagina ? 0 : cont.getBoundingClientRect().top;"
        "    var destino = ancla ? cont.scrollTop + ancla.getBoundingClientRect().top"
        f"                 - arriba - {_MARGEN_SUPERIOR} : 0;"
        "    cont.scrollTop = Math.max(0, destino);"
        "  });"
        "})();</script>"
    )
    st.html(script, unsafe_allow_javascript=True)


def chips(etiquetas: list[str], limite: int = 6) -> None:
    """Nombres en etiquetas redondas, con un '+N' si hay mas."""
    if not etiquetas:
        return
    html = "".join(f'<span class="sbc-chip">{e}</span>'
                   for e in etiquetas[:limite])
    if len(etiquetas) > limite:
        html += f'<span class="sbc-chip">+{len(etiquetas) - limite}</span>'
    st.markdown(html, unsafe_allow_html=True)


def bloque_fuentes(fuentes: list[dict]) -> None:
    """
    Las fuentes de una respuesta: primero los documentos (la pregunta
    frecuente es "de donde salio esto") y adentro cada pasaje.
    """
    if not fuentes:
        return
    documentos = []
    for f in fuentes:
        doc = f["etiqueta"].split(" · ")[0]
        if doc not in documentos:
            documentos.append(doc)
    with st.expander(f"De dónde salió ({len(documentos)})"):
        chips(documentos)
        st.markdown("")
        for f in fuentes:
            st.markdown(
                f'<div class="sbc-fuente"><b>{f["etiqueta"]}</b><br>'
                f'<span>{recortar(f["extracto"], 200)}</span></div>',
                unsafe_allow_html=True)


def metricas(pares: list[tuple[str, str]]) -> None:
    """Fila de indicadores. Hasta cuatro: mas de eso ya no se leen."""
    pares = pares[:4]
    if not pares:
        return
    for col, (etiqueta, valor) in zip(st.columns(len(pares)), pares):
        col.metric(etiqueta, valor)
