"""
nucleo/sugerencias.py
=====================
Las tres preguntas sugeridas que aparecen después de cada respuesta en
Conversar.

DE DÓNDE SALEN (decisión de la SBC, opción A): de los TÍTULOS de los
documentos que se usaron para responder. Por tres razones:
  · no cuestan nada extra (no se le pide nada al modelo);
  · funcionan aunque no haya modelo configurado (modo búsqueda);
  · siempre tienen respuesta en lo que está cargado. Una sugerencia que la
    app no sabe responder es peor que ninguna.

CÓMO SE ELIGEN
  1. Del fragmento que más se pareció a la pregunta NO se sugiere nada: lo
     más probable es que sea justo lo que se acaba de responder.
  2. Del resto, en orden de parecido, se toman las preguntas que aparecen
     como título («## 12. ¿Qué es la Septuaginta?») o como línea que
     empieza con «¿» y termina con «?».
  3. Se descarta lo que ya se preguntó en la conversación y lo que se le
     parece mucho (mismas palabras con otro orden o sin tildes).
  4. Si no se juntan tres, se completa con las preguntas de respaldo que da
     la pantalla (las del inicio), sin repetir.

Esto calcula; no dibuja. Los botones están en app/paginas/conversar.py.
"""
from __future__ import annotations

import re
import unicodedata

# Una pregunta al comienzo de una línea, con o sin «## 12.» delante.
_PATRON = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\d{1,4}[.)][ \t]*)?(¿[^\n¿?]{5,200}\?)",
                     re.MULTILINE)

# Palabras que no distinguen una pregunta de otra.
_VACIAS = {
    "que", "qué", "como", "cómo", "cual", "cuál", "cuales", "cuáles", "por", "para",
    "los", "las", "una", "uno", "unos", "unas", "del", "con", "sin", "sobre", "dice",
    "biblia", "esta", "este", "eso", "son", "hay", "mas", "más", "pero", "porque",
    "cuando", "donde", "quien", "quién", "todo", "toda", "sus", "les", "nos", "mis",
    "tus", "ser", "fue", "era", "segun", "según",
    # de dos letras: «fe» sí distingue una pregunta; estas no
    "es", "la", "el", "de", "en", "lo", "se", "un", "mi", "tu", "su", "me", "te",
    "le", "ya", "si", "al", "os", "ha", "he", "yo", "da",
}

# Desde cuánto se consideran «la misma pregunta» (proporción de palabras
# compartidas). 0,6 junta «¿Qué es la fe?» con «¿Qué es la fe según la
# Biblia?», pero no «¿Qué es la fe?» con «¿Qué es la gracia?».
UMBRAL_PARECIDO = 0.6


def _sin_tildes(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _palabras(texto: str) -> set[str]:
    limpio = re.sub(r"[^a-z0-9ñ ]", " ", _sin_tildes(texto))
    return {p for p in limpio.split() if len(p) > 1 and p not in _VACIAS}


def parecidas(a: str, b: str) -> bool:
    """True si dos preguntas son, a efectos prácticos, la misma."""
    pa, pb = _palabras(a), _palabras(b)
    if not pa or not pb:
        return _sin_tildes(a).strip() == _sin_tildes(b).strip()
    return len(pa & pb) / len(pa | pb) >= UMBRAL_PARECIDO


def preguntas_en(texto: str) -> list[str]:
    """Las preguntas que hay como título o línea propia en un texto."""
    return [" ".join(q.split()) for q in _PATRON.findall(str(texto or ""))]


def sugerir(fragmentos: list[str], pregunta: str, ya_hechas: list[str],
            respaldo: list[str], n: int = 3) -> list[str]:
    """
    Hasta `n` preguntas para seguir la conversación (ver el porqué arriba).

    fragmentos: los textos usados para responder, del más al menos parecido.
    pregunta:   la que se acaba de responder.
    ya_hechas:  las que la persona hizo antes en esta conversación.
    respaldo:   preguntas generales para completar si faltan.
    """
    vistas = [str(pregunta)] + [str(q) for q in (ya_hechas or [])]
    salida: list[str] = []

    def _sirve(q: str) -> bool:
        return not any(parecidas(q, v) for v in vistas + salida)

    fragmentos = [str(f) for f in (fragmentos or [])]
    excluidas = preguntas_en(fragmentos[0]) if fragmentos else []
    for frag in fragmentos[1:]:
        for q in preguntas_en(frag):
            if q in excluidas or not _sirve(q):
                continue
            salida.append(q)
            if len(salida) == n:
                return salida
    for q in respaldo or []:
        if len(salida) == n:
            break
        if _sirve(q):
            salida.append(q)
    return salida
