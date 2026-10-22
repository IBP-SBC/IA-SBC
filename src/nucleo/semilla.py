"""
nucleo/semilla.py
=================
Texto bíblico de EJEMPLO que viaja dentro del repositorio: el Nuevo
Testamento Reina-Valera 1909, de dominio público.

POR QUÉ EXISTE
--------------
Dos pantallas necesitan texto bíblico sin depender de que alguien lo
cargue: la Biblia de la SBC (mientras no se carguen sus versiones
oficiales) y la demo Millca (que muestra Juan). Un solo archivo y un solo
lector: Juan dejó de estar duplicado en dos CSV.

DE DÓNDE SALE Y QUÉ SE LE HIZO (procedencia completa)
-----------------------------------------------------
· Archivo fuente: spa-rv1909.usfx.xml del repositorio público open-bibles
  (github.com/seven1m/open-bibles), la Reina-Valera 1909 completa.
· Se extrajeron los 27 libros del Nuevo Testamento: 260 capítulos, la
  cuenta canónica, y 7.955 versículos con texto.
· 7.955 y no 7.957: en esta edición el texto de 2 Corintios 13:14 está
  dentro del 13:13, y el de Hechos 19:41 dentro del 19:40. El archivo
  trae esas dos marcas VACÍAS. No se inventa un versículo vacío para que
  la cuenta cuadre: la cuenta se explica.
· Se retiraron 14 notas finales de las epístolas ("Fué escrita de Corinto
  á los Romanos…"): no son texto bíblico, son añadiduras tardías que el
  archivo pegaba dentro del último versículo. Se cortó exactamente después
  del último "Amén." de esos 14 versículos.
· Los nombres de los libros se unificaron en su forma corta ("Mateo",
  "Lucas"); el archivo traía "San Mateo" y "San Lucas" pero "Marcos" y
  "Juan".
· Juan 3:16 y 14:6 se cotejaron letra por letra contra el evangelio de
  Juan de 1909 publicado en Project Gutenberg (libro 5881): coinciden.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from nucleo.config import ROOT

RUTA_NT_RV1909 = ROOT / "data" / "semilla" / "nt_rv1909.csv"
COLUMNAS = ["version", "libro", "orden", "capitulo", "versiculo", "texto"]
VERSION = "RV1909"


@lru_cache(maxsize=2)
def _leer(ruta: str, _mtime: float) -> pd.DataFrame:
    """Lectura cacheada; el mtime entra solo para invalidar si el archivo cambia."""
    return pd.read_csv(ruta, encoding="utf-8")


def nuevo_testamento() -> pd.DataFrame:
    """
    El Nuevo Testamento RV1909 completo. Vacío si el archivo no está o no
    tiene las columnas esperadas (la pantalla que lo use lo dice).

    Se devuelve una COPIA: el resultado viene de un caché y quien lo use
    no debe poder modificarlo para los demás.
    """
    if not RUTA_NT_RV1909.exists():
        return pd.DataFrame(columns=COLUMNAS)
    try:
        df = _leer(str(RUTA_NT_RV1909), RUTA_NT_RV1909.stat().st_mtime)
    except Exception:
        return pd.DataFrame(columns=COLUMNAS)
    if any(c not in df.columns for c in COLUMNAS):
        return pd.DataFrame(columns=COLUMNAS)
    return df.copy()


def libro(nombre: str) -> pd.DataFrame:
    """Un libro del Nuevo Testamento de ejemplo (p. ej. 'Juan')."""
    df = nuevo_testamento()
    return df[df["libro"].astype(str) == str(nombre)].reset_index(drop=True)
