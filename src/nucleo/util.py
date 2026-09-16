"""
nucleo/util.py
==============
Utilidades transversales: hora de Bogotá, normalización de texto para la
búsqueda, tamaños legibles y escape de markdown.

Todo acá es defensivo: ninguna función de este módulo debe poder tumbar
la app.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from nucleo.config import TZ_BOGOTA


# ════════════════════════════════════════════════════════════════════
# TIEMPO
# ════════════════════════════════════════════════════════════════════

def ahora_bogota() -> datetime:
    """
    Fecha y hora actual en Bogotá.

    Se intenta con zoneinfo (respeta cambios de norma) y, si el sistema
    no trae la base de datos de zonas horarias, se cae a UTC-5 fijo:
    Colombia no tiene horario de verano, así que el resultado es el
    mismo. Nunca lanza excepción.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(TZ_BOGOTA))
    except Exception:
        return datetime.now(timezone(timedelta(hours=-5)))


def sello_ahora() -> str:
    """Sello de tiempo guardable: '2026-09-12 14:07' (hora de Bogotá)."""
    return ahora_bogota().strftime("%Y-%m-%d %H:%M")


def sello_legible(texto: str | None) -> str:
    """
    Convierte un sello guardado a algo que se lee en pantalla.
    Si no hay sello, lo dice en vez de mostrar un vacío ambiguo.
    """
    if not texto:
        return "sin registro"
    try:
        dt = datetime.strptime(str(texto)[:16], "%Y-%m-%d %H:%M")
        meses = ["ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic"]
        return f"{dt.day} {meses[dt.month - 1]} {dt.year}, {dt:%H:%M}"
    except Exception:
        return str(texto)


# ════════════════════════════════════════════════════════════════════
# TEXTO
# ════════════════════════════════════════════════════════════════════

# Palabras vacías del español. Se quitan SOLO para buscar; el texto que
# se le muestra al modelo va siempre completo y original.
STOPWORDS = {
    "a", "al", "algo", "algunos", "ante", "antes", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "dos", "el", "ella",
    "ellos", "en", "entre", "era", "es", "esa", "ese", "eso", "esta",
    "este", "esto", "ha", "hace", "han", "hasta", "hay", "la", "las", "le",
    "les", "lo", "los", "mas", "me", "mi", "mucho", "muy", "no", "nos",
    "o", "otra", "otro", "para", "pero", "poco", "por", "porque", "que",
    "quien", "se", "ser", "si", "sin", "sobre", "solo", "son", "su", "sus",
    "tambien", "tanto", "te", "tiene", "todo", "tu", "un", "una", "uno",
    "unos", "y", "ya",
}


def normalizar(texto: str) -> str:
    """
    Minúsculas y sin tildes. 'Biblia' y 'biblía' deben encontrar lo mismo:
    en los documentos de la SBC conviven las dos formas.
    """
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower()


def raiz_ligera(palabra: str) -> str:
    """
    Recorte conservador de PLURALES. No es un lematizador: solo quita la
    's' y el 'es' finales de palabras largas.

    POR QUÉ: sin esto, "¿qué dicen los estudios sobre los jóvenes?" no
    encuentra un párrafo que habla de "el joven" y "el estudio". Es el
    fallo más común de una búsqueda por palabras en español.

    Se aplica IGUAL al indexar y al preguntar, así que aunque un recorte
    quede raro ("analisis" → "analisi"), los dos lados quedan iguales y
    el cruce funciona. Lo que NO hace: tocar números ni códigos, ni
    adivinar familias de palabras ("juventud" no se vuelve "joven").
    """
    p = palabra
    if any(c.isdigit() for c in p):
        return p                      # '0001', ISBN y cifras van intactos
    if len(p) > 5 and p.endswith("es"):
        return p[:-2]
    if len(p) > 4 and p.endswith("s") and not p.endswith("ss"):
        return p[:-1]
    return p


def tokenizar(texto: str, quitar_stopwords: bool = True) -> list[str]:
    """
    Parte un texto en palabras buscables. Conserva números y códigos
    (un ISBN o un '0001' son datos, no ruido) y unifica singular/plural.
    """
    t = normalizar(texto)
    palabras = re.findall(r"[a-z0-9áéíóúñ_]+", t)
    if quitar_stopwords:
        palabras = [p for p in palabras if p not in STOPWORDS and len(p) > 1]
    return [raiz_ligera(p) for p in palabras]


def sha_bytes(contenido: bytes) -> str:
    """Huella del archivo: sirve para saber si un archivo REALMENTE cambió."""
    return hashlib.sha256(contenido).hexdigest()[:16]


def tam_legible(n_bytes: int | float | None) -> str:
    """1536000 → '1,5 MB' (formato colombiano: coma decimal)."""
    try:
        n = float(n_bytes or 0)
    except Exception:
        return "—"
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            txt = f"{n:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".")
            return f"{txt} {unidad}"
        n /= 1024
    return "—"


def esc_md(texto: str) -> str:
    """
    Escapa el '$' para que markdown no interprete un monto como fórmula
    LaTeX y se coma medio párrafo ($41.386.063.026 desaparecía).
    """
    return str(texto).replace("$", r"\$")


def recortar(texto: str, n: int = 160) -> str:
    """Recorta con puntos suspensivos, sin cortar a mitad de palabra."""
    t = " ".join(str(texto).split())
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0] + "…"
