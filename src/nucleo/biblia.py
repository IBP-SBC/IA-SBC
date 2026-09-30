"""
nucleo/biblia.py
================
El texto bíblico para leer en la app.

POR QUÉ ES UN MÓDULO APARTE Y NO UN DOCUMENTO MÁS:
un documento del índice se parte en fragmentos para BUSCAR. La Biblia se
LEE: hay que poder abrir un libro, moverse al capítulo siguiente y citar
un versículo exacto. Eso necesita una estructura propia —versión, libro,
capítulo, versículo— y no un montón de fragmentos de 1.200 caracteres.

FORMATO DEL CORPUS (data/estado/biblia.parquet):
  version    RVR | TLA
  libro      nombre canónico ("Filipenses")
  orden      número del libro, para ordenar (1 = Génesis)
  capitulo   entero
  versiculo  entero
  texto      el versículo

DE DÓNDE SALE: de los PDF originales de la SBC, que son de la casa. La
extracción NO se hace acá: se hace una vez con herramientas/extraer_biblia.py
y se revisa contra el impreso antes de publicarla. Un error de extracción
en un versículo no es un bug de software, es un texto bíblico mal citado.
"""
from __future__ import annotations

import pandas as pd

from nucleo import nube
from nucleo.config import ESTADO_DIR

ARCHIVO_BIBLIA = "biblia.parquet"
RUTA_BIBLIA = ESTADO_DIR / ARCHIVO_BIBLIA

COLUMNAS = ["version", "libro", "orden", "capitulo", "versiculo", "texto"]


def leer_corpus() -> pd.DataFrame:
    """Corpus completo. Vacío si todavía no se ha cargado ningún texto."""
    if not RUTA_BIBLIA.exists():
        nube.bajar_archivo(nube.clave_estado(ARCHIVO_BIBLIA), RUTA_BIBLIA)
    if not RUTA_BIBLIA.exists():
        return pd.DataFrame(columns=COLUMNAS)
    try:
        df = pd.read_parquet(RUTA_BIBLIA)
    except Exception:
        return pd.DataFrame(columns=COLUMNAS)
    return df if all(c in df.columns for c in COLUMNAS) else pd.DataFrame(columns=COLUMNAS)


def hay_texto() -> bool:
    return not leer_corpus().empty


def guardar_corpus(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Guarda el corpus validando lo mínimo indispensable.

    No se guarda un corpus incompleto en silencio: si faltan columnas o
    vienen versículos sin texto, se dice cuántos y no se escribe. Publicar
    una Biblia con huecos es peor que no publicarla.
    """
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        return False, "Al corpus le faltan columnas: " + ", ".join(faltan)
    vacios = int(df["texto"].isna().sum() + (df["texto"].astype(str).str.strip() == "").sum())
    if vacios:
        return False, (f"Hay {vacios} versículos sin texto. Revisá la "
                       "extracción antes de publicar.")
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    df[COLUMNAS].to_parquet(RUTA_BIBLIA, index=False)
    ok = nube.subir_archivo(RUTA_BIBLIA, nube.clave_estado(ARCHIVO_BIBLIA))
    resumen = (f"Cargados {len(df):,} versículos de "
               f"{df['libro'].nunique()} libros.").replace(",", ".")
    return True, resumen + ("" if ok else " OJO: no se respaldó en la nube.")


# ── Consultas para la pantalla de lectura ────────────────────────────

def versiones() -> list[str]:
    df = leer_corpus()
    return [] if df.empty else sorted(df["version"].astype(str).unique())


def libros(version: str) -> list[str]:
    """Libros de una versión, en el orden bíblico y no alfabético."""
    df = leer_corpus()
    if df.empty:
        return []
    df = df[df["version"].astype(str) == str(version)]
    if df.empty:
        return []
    orden = (df[["libro", "orden"]].drop_duplicates()
             .sort_values("orden")["libro"].astype(str).tolist())
    return orden


def capitulos(version: str, libro: str) -> list[int]:
    df = leer_corpus()
    if df.empty:
        return []
    df = df[(df["version"].astype(str) == str(version))
            & (df["libro"].astype(str) == str(libro))]
    return sorted(int(c) for c in df["capitulo"].dropna().unique())


def capitulo(version: str, libro: str, numero: int) -> pd.DataFrame:
    """Los versículos de un capítulo, ordenados."""
    df = leer_corpus()
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    sel = df[(df["version"].astype(str) == str(version))
             & (df["libro"].astype(str) == str(libro))
             & (pd.to_numeric(df["capitulo"], errors="coerce") == int(numero))]
    return sel.sort_values("versiculo").reset_index(drop=True)


def buscar_texto(consulta: str, version: str | None = None,
                 limite: int = 30) -> pd.DataFrame:
    """
    Busca una frase en el texto bíblico.

    Es una búsqueda literal sobre el texto, sin tildes ni mayúsculas: el
    lector que escribe "todo lo puedo" espera encontrar ese versículo, no
    una interpretación. Lo que no aparece, no aparece.
    """
    from nucleo.util import normalizar

    df = leer_corpus()
    if df.empty or not str(consulta).strip():
        return pd.DataFrame(columns=COLUMNAS)
    if version:
        df = df[df["version"].astype(str) == str(version)]
    patron = normalizar(consulta).strip()
    mascara = df["texto"].astype(str).map(lambda t: patron in normalizar(t))
    return df[mascara].head(int(limite)).reset_index(drop=True)


def referencia(fila) -> str:
    """'Filipenses 4:6' a partir de una fila del corpus."""
    return f"{fila['libro']} {int(fila['capitulo'])}:{int(fila['versiculo'])}"


def resumen() -> dict:
    """Cifras para la pantalla de administración."""
    df = leer_corpus()
    if df.empty:
        return {"versiones": 0, "libros": 0, "versiculos": 0, "detalle": []}
    detalle = []
    for v in sorted(df["version"].astype(str).unique()):
        sub = df[df["version"].astype(str) == v]
        detalle.append({"version": v, "libros": int(sub["libro"].nunique()),
                        "versiculos": int(len(sub))})
    return {"versiones": df["version"].nunique(),
            "libros": int(df["libro"].nunique()),
            "versiculos": int(len(df)), "detalle": detalle}
