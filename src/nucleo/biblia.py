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
extracción NO se hace acá: se hace una vez y se revisa contra el impreso
antes de publicarla. Un error de extracción en un versículo no es un bug
de software, es un texto bíblico mal citado.

MIENTRAS NO HAYA TEXTO OFICIAL se muestra el Nuevo Testamento Reina-Valera
1909 de ejemplo (dominio público, ver nucleo/semilla.py). Es un respaldo,
no una versión más: en cuanto el administrador carga el corpus de la SBC,
el ejemplo deja de mostrarse. La pantalla dice siempre cuál está viendo.
"""
from __future__ import annotations

import pandas as pd

from functools import lru_cache

from nucleo import nube, semilla
from nucleo.config import ESTADO_DIR

ARCHIVO_BIBLIA = "biblia.parquet"
RUTA_BIBLIA = ESTADO_DIR / ARCHIVO_BIBLIA

COLUMNAS = ["version", "libro", "orden", "capitulo", "versiculo", "texto"]


@lru_cache(maxsize=2)
def _leer_oficial(ruta: str, _mtime: float) -> pd.DataFrame:
    """Lectura cacheada del corpus oficial; el mtime invalida si cambia."""
    return pd.read_parquet(ruta)


def _corpus_oficial() -> pd.DataFrame:
    """El corpus que cargó el administrador. Vacío si no hay."""
    if not RUTA_BIBLIA.exists():
        # Una descarga por llamada sería lenta: la nube recuerda por un
        # minuto los archivos que no existen (ver nube._NO_EXISTE).
        nube.bajar_archivo(nube.clave_estado(ARCHIVO_BIBLIA), RUTA_BIBLIA)
    if not RUTA_BIBLIA.exists():
        return pd.DataFrame(columns=COLUMNAS)
    try:
        df = _leer_oficial(str(RUTA_BIBLIA), RUTA_BIBLIA.stat().st_mtime)
    except Exception:
        return pd.DataFrame(columns=COLUMNAS)
    return df.copy() if all(c in df.columns for c in COLUMNAS) \
        else pd.DataFrame(columns=COLUMNAS)


def es_ejemplo() -> bool:
    """True si se está mostrando el texto de ejemplo y no el oficial."""
    return _corpus_oficial().empty and not semilla.nuevo_testamento().empty


def leer_corpus() -> pd.DataFrame:
    """
    El texto a mostrar: el oficial de la SBC si está cargado; si no, el
    Nuevo Testamento RV1909 de ejemplo. Vacío solo si no hay ninguno.
    """
    oficial = _corpus_oficial()
    return oficial if not oficial.empty else semilla.nuevo_testamento()


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


def vecinos(version: str, libro: str, numero: int) -> tuple:
    """
    Capítulo anterior y siguiente, CRUZANDO libros: después de Mateo 28
    viene Marcos 1. Devuelve ((libro, cap) | None, (libro, cap) | None).

    Así se lee de corrido sin volver al selector cada vez que termina un
    libro, que es como se lee una Biblia de papel.
    """
    df = leer_corpus()
    if df.empty:
        return None, None
    df = df[df["version"].astype(str) == str(version)]
    orden = (df[["orden", "libro", "capitulo"]].drop_duplicates()
             .sort_values(["orden", "capitulo"]))
    pares = [(str(l), int(c)) for l, c in zip(orden["libro"], orden["capitulo"])]
    try:
        i = pares.index((str(libro), int(numero)))
    except ValueError:
        return None, None
    anterior = pares[i - 1] if i > 0 else None
    siguiente = pares[i + 1] if i < len(pares) - 1 else None
    return anterior, siguiente


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
        return {"versiones": 0, "libros": 0, "versiculos": 0, "detalle": [],
                "es_ejemplo": False}
    detalle = []
    for v in sorted(df["version"].astype(str).unique()):
        sub = df[df["version"].astype(str) == v]
        detalle.append({"version": v, "libros": int(sub["libro"].nunique()),
                        "versiculos": int(len(sub))})
    return {"versiones": df["version"].nunique(),
            "libros": int(df["libro"].nunique()),
            "versiculos": int(len(df)), "detalle": detalle,
            "es_ejemplo": es_ejemplo()}
