"""
app/ui.py
=========
La cara de la app: estilo, encabezados y piezas visuales que se repiten.

TRES REGLAS QUE MANDAN ACÁ

1. **Funciona en claro y en oscuro.** No se define `[theme]` en
   config.toml (eso forzaría el modo claro para todos) y no se usan
   colores de fondo fijos. Los acentos van con transparencias sobre el
   fondo del tema, así nunca hay texto claro sobre fondo claro.
2. **Menos es más.** Nada de sombras, degradados ni animaciones. Lo que
   se busca es que el contenido se lea rápido: jerarquía clara, aire
   entre bloques y un solo color de acento, el azul institucional.
3. **Esto dibuja, no calcula.** Ninguna función de acá decide nada del
   negocio.
"""
from __future__ import annotations

import streamlit as st

from nucleo.config import COLOR_ACENTO, COLOR_PRIMARIO
from nucleo.util import recortar

# El CSS va en una sola cadena y se aplica UNA vez por página. Cada regla
# tiene un motivo; las que no lo tengan, sobran.
_CSS = f"""
<style>
/* Un poco de aire arriba: el título pegado al borde se lee apretado. */
.block-container {{ padding-top: 2.2rem; max-width: 1100px; }}

/* Títulos más compactos y con mejor jerarquía entre nivel 2 y 3. */
h1, h2, h3 {{ letter-spacing: -0.01em; }}
h2 {{ margin-bottom: 0.2rem; }}

/* Encabezado de página: una barra azul a la izquierda en vez de una
   línea horizontal, que ocupa menos y ordena la lectura. */
.sbc-encabezado {{
  border-left: 4px solid {COLOR_PRIMARIO};
  padding: 0.1rem 0 0.1rem 0.8rem;
  margin: 0 0 1.1rem 0;
}}
.sbc-encabezado .t {{ font-size: 1.45rem; font-weight: 650; line-height: 1.25; }}
.sbc-encabezado .s {{ font-size: 0.92rem; opacity: 0.72; }}

/* Fuentes citadas: franja azul e interlineado cómodo. Se leen como una
   cita, que es lo que son. */
.sbc-fuente {{
  border-left: 3px solid {COLOR_ACENTO}66;
  padding: 0.15rem 0 0.15rem 0.7rem;
  margin: 0.45rem 0;
  font-size: 0.88rem;
}}
.sbc-fuente b {{ font-size: 0.9rem; }}
.sbc-fuente span {{ opacity: 0.72; }}

/* Etiquetas redondas para nombrar documentos sin gastar una línea. */
.sbc-chip {{
  display: inline-block;
  padding: 0.12rem 0.55rem;
  margin: 0.12rem 0.25rem 0.12rem 0;
  border: 1px solid {COLOR_ACENTO}55;
  background: {COLOR_ACENTO}14;
  border-radius: 999px;
  font-size: 0.78rem;
}}

/* Botón principal en el azul institucional. */
.stButton > button[kind="primary"] {{
  background-color: {COLOR_PRIMARIO};
  border-color: {COLOR_PRIMARIO};
}}

/* Burbujas del chat con un borde suave: separa visualmente pregunta y
   respuesta sin pintar fondos que pelean con el tema. */
[data-testid="stChatMessage"] {{
  border: 1px solid rgba(128,128,128,0.18);
  border-radius: 12px;
  padding: 0.6rem 0.9rem;
  margin-bottom: 0.5rem;
}}

/* Separación clara entre el panel lateral y el contenido. */
[data-testid="stSidebar"] {{ border-right: 1px solid rgba(128,128,128,0.18); }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

/* La caja de escribir, siempre visible y con el acento institucional. */
[data-testid="stChatInput"] textarea {{ font-size: 0.97rem; }}
</style>
"""


def aplicar_estilo() -> None:
    """Inyecta el CSS. Se llama una vez, desde Home.py."""
    st.markdown(_CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str = "", icono: str = "") -> None:
    """Encabezado de página, igual en todas para que no haya sorpresas."""
    tit = f"{icono} {titulo}".strip()
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(
        f'<div class="sbc-encabezado"><div class="t">{tit}</div>{sub}</div>',
        unsafe_allow_html=True)


def chips(etiquetas: list[str], limite: int = 6) -> None:
    """Lista de nombres en etiquetas redondas, con un '+N' si hay más."""
    if not etiquetas:
        return
    visibles = etiquetas[:limite]
    html = "".join(f'<span class="sbc-chip">{e}</span>' for e in visibles)
    if len(etiquetas) > limite:
        html += f'<span class="sbc-chip">+{len(etiquetas) - limite}</span>'
    st.markdown(html, unsafe_allow_html=True)


def bloque_fuentes(fuentes: list[dict]) -> None:
    """
    Las fuentes de una respuesta. Primero los documentos como etiquetas
    (la pregunta más frecuente es "¿de dónde salió esto?", y se responde
    de un vistazo) y adentro el extracto de cada pasaje.
    """
    if not fuentes:
        return
    documentos = []
    for f in fuentes:
        doc = f["etiqueta"].split(" · ")[0]
        if doc not in documentos:
            documentos.append(doc)
    with st.expander(f"📎 {len(fuentes)} pasajes de {len(documentos)} documento(s)"):
        chips(documentos)
        st.markdown("")
        for f in fuentes:
            st.markdown(
                f'<div class="sbc-fuente"><b>{f["etiqueta"]}</b><br>'
                f'<span>{recortar(f["extracto"], 220)}</span></div>',
                unsafe_allow_html=True)


def metricas(pares: list[tuple[str, str]]) -> None:
    """Fila de indicadores. Hasta cuatro: más de eso ya no se leen."""
    pares = pares[:4]
    if not pares:
        return
    for col, (etiqueta, valor) in zip(st.columns(len(pares)), pares):
        col.metric(etiqueta, valor)
