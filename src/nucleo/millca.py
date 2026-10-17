"""
nucleo/millca.py
================
Motor de la DEMO para Comunidad Millca: una maqueta de los tres botones
de la propuesta (La Palabra · Inspiración Diaria · Mi Altar Digital) que
vive dentro de IA-SBC en una dirección aparte y no toca nada de la SBC.

POR QUÉ ES UN MÓDULO PROPIO Y NO REUTILIZA biblia.py
----------------------------------------------------
biblia.py lee el corpus de la SBC (RVR/TLA, cargado por el admin y
guardado en Supabase). La demo necesita un texto que exista SIN que nadie
cargue nada y SIN pregunta de derechos: la Reina-Valera 1909, de dominio
público, que viaja en el repo en data/semilla/juan_rv1909.csv. Mezclar los
dos corpus habría obligado a que la demo dependiera de la nube de la SBC
y a que un texto de dominio público apareciera como "versión de la casa".

FUENTE DEL TEXTO
  Reina-Valera 1909 · dominio público · archivo spa-rv1909.usfx.xml del
  repositorio open-bibles (github.com/seven1m/open-bibles). Se extrajo
  SOLO el evangelio de Juan: 879 versículos en 21 capítulos, la cuenta
  canónica. La ortografía antigua ("á", "fué") es la original de 1909.

Los videos y los textos del perfil se configuran en Configuración →
Millca y se guardan en el bucket, para poder cambiarlos desde el celular
sin redesplegar.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from nucleo import nube
from nucleo.config import ESTADO_DIR, ROOT

# La semilla se ancla a la RAÍZ del repo, no a data/: es texto de dominio
# público que forma parte del código (como un geojson), no un dato de la
# SBC que viva en Supabase. Por eso también está fuera del .gitignore.
RUTA_SEMILLA = ROOT / "data" / "semilla" / "juan_rv1909.csv"
ARCHIVO_PARAMS = "millca.json"

COLUMNAS = ["version", "libro", "orden", "capitulo", "versiculo", "texto"]

# ── Valores de fábrica: lo que se ve si nadie configuró nada ─────────
# Los videos son los que entregó Alberto para la demo (17-oct-2026): dos
# de un canal personal de YouTube como muestra y los tres reels más vistos
# de la cuenta real de Millca. Se cambian desde Configuración → Millca
# sin tocar código.
PARAMS_DEFECTO = {
    "nombre_app": "Comunidad Millca",
    "lema": "La Palabra, cada día, contigo",
    "nombre_usuaria": "Chica Millca",
    "ciudad": "Bogotá",
    "instagram_perfil": "https://www.instagram.com/millcadesign",
    "videos": [            # lista de {"titulo": str, "url": str}
        {"titulo": "Reel · Millca", "url": "https://www.instagram.com/reel/DAVvKsFOzeQ/"},
        {"titulo": "Reel · Millca", "url": "https://www.instagram.com/reel/C5M_0MXMwqf/"},
        {"titulo": "Reel · Millca", "url": "https://www.instagram.com/reel/C3Ni6EeLhfI/"},
        {"titulo": "Devocional en video", "url": "https://youtu.be/Rp3F9AggYAI"},
        {"titulo": "Devocional en video", "url": "https://youtu.be/HnoYPN_kuCI"},
    ],
    "racha_dias": 7,       # dato ILUSTRATIVO del perfil de la demo
    "capitulos_leidos": 12,
    "notas_guardadas": 5,
}


# ════════════════════════════════════════════════════════════════════
# TEXTO BÍBLICO DE LA DEMO
# ════════════════════════════════════════════════════════════════════

def leer_corpus() -> pd.DataFrame:
    """El evangelio de Juan RV1909. Vacío (y lo dice) si falta la semilla."""
    if not RUTA_SEMILLA.exists():
        return pd.DataFrame(columns=COLUMNAS)
    try:
        df = pd.read_csv(RUTA_SEMILLA, encoding="utf-8")
    except Exception:
        return pd.DataFrame(columns=COLUMNAS)
    if any(c not in df.columns for c in COLUMNAS):
        return pd.DataFrame(columns=COLUMNAS)
    return df


def capitulos() -> list[int]:
    df = leer_corpus()
    return sorted(int(c) for c in df["capitulo"].unique()) if not df.empty else []


def capitulo(numero: int) -> pd.DataFrame:
    df = leer_corpus()
    if df.empty:
        return df
    sel = df[pd.to_numeric(df["capitulo"], errors="coerce") == int(numero)]
    return sel.sort_values("versiculo").reset_index(drop=True)


# Versículos de Juan que SÍ funcionan como tarjeta de bienvenida. La
# selección automática por longitud entregó Juan 7:52 ("¿Eres tú también
# Galileo?") como versículo del día: corto, sí; de bienvenida, no. Una
# lista curada por una persona es la única forma de garantizar el tono.
VERSICULOS_DEL_DIA = [
    (1, 5), (1, 12), (3, 16), (3, 17), (4, 14), (6, 35), (8, 12), (8, 32),
    (10, 10), (10, 11), (11, 25), (13, 34), (14, 1), (14, 6), (14, 27),
    (15, 5), (15, 9), (15, 12), (16, 33), (20, 29), (21, 25),
]


def versiculo_del_dia() -> dict | None:
    """
    Un versículo fijo por día (no aleatorio): si dos directivas abren la
    app el mismo día, ven lo mismo, y eso es lo que haría la app real.
    """
    from nucleo.util import ahora_bogota

    df = leer_corpus()
    if df.empty:
        return None
    cap, ver = VERSICULOS_DEL_DIA[ahora_bogota().timetuple().tm_yday % len(VERSICULOS_DEL_DIA)]
    sel = df[(pd.to_numeric(df["capitulo"], errors="coerce") == cap)
             & (pd.to_numeric(df["versiculo"], errors="coerce") == ver)]
    if sel.empty:
        return None
    fila = sel.iloc[0]
    return {"referencia": f"{fila['libro']} {cap}:{ver}", "texto": str(fila["texto"])}


def resumen_corpus() -> dict:
    df = leer_corpus()
    return {"versiculos": int(len(df)),
            "capitulos": int(df["capitulo"].nunique()) if not df.empty else 0}


# ════════════════════════════════════════════════════════════════════
# PARÁMETROS (videos, nombre, perfil) — se guardan en el bucket
# ════════════════════════════════════════════════════════════════════

def leer_parametros() -> dict:
    """Parámetros guardados, completados con los de fábrica si falta algo."""
    datos = nube.leer_json_remoto(ARCHIVO_PARAMS)
    if datos is None:
        ruta = ESTADO_DIR / ARCHIVO_PARAMS
        if ruta.exists():
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except Exception:
                datos = {}
        else:
            datos = {}
    salida = dict(PARAMS_DEFECTO)
    salida.update({k: v for k, v in (datos or {}).items() if v is not None})
    return salida


def guardar_parametros(cambios: dict) -> str:
    """Guarda en disco y en la nube. Devuelve un mensaje para pantalla."""
    params = leer_parametros()
    params.update(cambios)
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    cuerpo = json.dumps(params, ensure_ascii=False, indent=2)
    (ESTADO_DIR / ARCHIVO_PARAMS).write_text(cuerpo, encoding="utf-8")
    ok = nube.subir_bytes(nube.clave_estado(ARCHIVO_PARAMS), cuerpo.encode("utf-8"))
    if not nube.nube_activa():
        return "Guardado en este servidor. Sin nube, se pierde al reiniciar."
    return "Guardado." if ok else "Guardado en disco, pero falló la subida a la nube."


# ════════════════════════════════════════════════════════════════════
# VIDEOS: reconocer el enlace y armar el reproductor incrustado
# ════════════════════════════════════════════════════════════════════

def clasificar_video(url: str) -> dict:
    """
    Dado un enlace, dice de qué plataforma es y cómo incrustarlo.

    Devuelve {'plataforma', 'embed', 'url', 'aviso'}.
      · YouTube: se extrae el ID y se usa el reproductor embebido.
      · Instagram: se usa el embed oficial de la publicación. OJO: solo
        funciona con publicaciones PÚBLICAS, y a veces Instagram muestra
        una tarjeta con "Ver en Instagram" en vez del video. Eso lo
        decide Instagram, no la app; se avisa en pantalla.
      · Otro: se muestra como enlace.
    """
    url = (url or "").strip()
    if not url:
        return {"plataforma": "", "embed": "", "url": "", "aviso": "Enlace vacío."}
    p = urlparse(url if "//" in url else "https://" + url)
    host = (p.netloc or "").lower().replace("www.", "")

    if host in ("youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com"):
        vid = ""
        if host == "youtu.be":
            vid = p.path.strip("/").split("/")[0]
        elif p.path.startswith("/shorts/") or p.path.startswith("/embed/"):
            vid = p.path.split("/")[2] if len(p.path.split("/")) > 2 else ""
        else:
            vid = parse_qs(p.query).get("v", [""])[0]
        vid = re.sub(r"[^A-Za-z0-9_-]", "", vid)
        if not vid:
            return {"plataforma": "youtube", "embed": "", "url": url,
                    "aviso": "No pude leer el ID del video de YouTube en ese enlace."}
        return {"plataforma": "youtube", "url": url, "aviso": "",
                "embed": f"https://www.youtube-nocookie.com/embed/{vid}"}

    if host in ("instagram.com", "instagr.am"):
        partes = [s for s in p.path.split("/") if s]
        # /p/<id>/ · /reel/<id>/ · /tv/<id>/
        if len(partes) >= 2 and partes[0] in ("p", "reel", "reels", "tv"):
            tipo = "reel" if partes[0] in ("reel", "reels") else partes[0]
            codigo = re.sub(r"[^A-Za-z0-9_-]", "", partes[1])
            return {"plataforma": "instagram", "url": url,
                    "embed": f"https://www.instagram.com/{tipo}/{codigo}/embed/",
                    "aviso": ("Instagram solo incrusta publicaciones públicas y a "
                              "veces muestra una tarjeta para abrirlo en su app.")}
        return {"plataforma": "instagram", "embed": "", "url": url,
                "aviso": "El enlace de Instagram tiene que ser de una publicación "
                         "o un reel (instagram.com/p/… o /reel/…)."}

    return {"plataforma": "otro", "embed": "", "url": url,
            "aviso": "Solo incrusto YouTube e Instagram; este queda como enlace."}
