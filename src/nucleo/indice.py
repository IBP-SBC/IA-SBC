"""
nucleo/indice.py
================
El "cerebro documental": qué documentos hay, en qué fragmentos se
partieron y cuáles responden mejor a una pregunta.

DECISIÓN DE DISEÑO (simplicidad de Jobs): la búsqueda es LÉXICA (BM25),
no vectorial. Por qué:
  · No necesita una segunda cuenta ni una segunda API key ni un costo por
    documento indexado. Se despliega hoy.
  · Es EXPLICABLE: se puede mostrar por qué un fragmento salió elegido.
    Un embedding es una caja negra y acá el usuario quiere trazabilidad.
  · El vocabulario de la SBC es muy específico (Patmos, S5, encuadernación,
    ISBN, "momento del portafolio"): son justo los términos raros que BM25
    puntúa mejor.
Cuando el corpus crezca y aparezcan preguntas con sinónimos que BM25 no
alcanza, el paso siguiente es agregar embeddings y mezclar los dos
puntajes. El contrato de buscar() no tendría que cambiar.

UPSERT POR NOMBRE DE ARCHIVO: subir dos veces "Plan 2026.pdf" ACTUALIZA
ese documento (se borran sus fragmentos viejos y se reindexa). El nombre
del archivo es la identidad del documento. No se adivinan identidades
parecidas: "Plan 2026.pdf" y "Plan 2026 v2.pdf" son DOS documentos.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from nucleo import nube
from nucleo.config import (
    DOCS_DIR,
    ESTADO_DIR,
    RUTA_CHUNKS,
    RUTA_REGISTRO,
    SOLAPE_FRAGMENTO,
    TAM_FRAGMENTO,
)
from nucleo.extraccion import extraer
from nucleo.util import sello_ahora, sha_bytes, tokenizar

# Nombres de los objetos de estado en el bucket (fuente única).
ARCHIVO_REGISTRO = "registro.json"
ARCHIVO_CHUNKS = "fragmentos.parquet"

COLUMNAS_CHUNKS = ["documento", "orden", "ubicacion", "texto"]


# ════════════════════════════════════════════════════════════════════
# REGISTRO DE DOCUMENTOS
# ════════════════════════════════════════════════════════════════════

def leer_registro() -> dict:
    """
    Devuelve {nombre_archivo: metadatos}.

    Regla 3.8: si no está en disco, se intenta traer de la nube ANTES de
    declararlo inexistente. Declarar "primera carga" solo porque falta el
    archivo local es exactamente lo que borró histórico tres veces.
    """
    if not RUTA_REGISTRO.exists():
        remoto = nube.leer_json_remoto(ARCHIVO_REGISTRO)
        if remoto is not None:
            _escribir_registro_local(remoto)
            return remoto
        return {}
    try:
        return json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _escribir_registro_local(registro: dict) -> None:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    RUTA_REGISTRO.write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")


def guardar_registro(registro: dict, permitir_reduccion: bool = False) -> str:
    """
    Escribe el registro en disco y lo sube con guarda. Devuelve el mensaje
    de la nube para mostrarlo en pantalla (nada falla en silencio).
    """
    _escribir_registro_local(registro)
    _ok, msg = nube.subir_json_con_guarda(
        ARCHIVO_REGISTRO, registro, permitir_reduccion=permitir_reduccion)
    return msg


# ════════════════════════════════════════════════════════════════════
# FRAGMENTOS
# ════════════════════════════════════════════════════════════════════

def leer_chunks() -> pd.DataFrame:
    """Índice completo. Si falta en disco, se intenta bajar de la nube."""
    if not RUTA_CHUNKS.exists():
        nube.bajar_archivo(nube.clave_estado(ARCHIVO_CHUNKS), RUTA_CHUNKS)
    if not RUTA_CHUNKS.exists():
        return pd.DataFrame(columns=COLUMNAS_CHUNKS)
    try:
        df = pd.read_parquet(RUTA_CHUNKS)
        faltan = [c for c in COLUMNAS_CHUNKS if c not in df.columns]
        if faltan:
            return pd.DataFrame(columns=COLUMNAS_CHUNKS)
        return df
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_CHUNKS)


def _guardar_chunks(df: pd.DataFrame) -> bool:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(RUTA_CHUNKS, index=False)
    except Exception:
        return False
    return nube.subir_archivo(RUTA_CHUNKS, nube.clave_estado(ARCHIVO_CHUNKS))


def _ubicacion(texto: str) -> str:
    """
    Devuelve la marca de página/hoja/diapositiva que traiga el fragmento,
    para poder citar 'Informe 2025 · Página 12' y no solo el archivo.
    """
    import re
    m = re.search(r"\[(Página|Hoja|Diapositiva)[:\s]*([^\]]+)\]", texto)
    return f"{m.group(1)} {m.group(2).strip()}" if m else ""


def trocear(texto: str) -> list[str]:
    """
    Parte el texto en fragmentos de ~TAM_FRAGMENTO caracteres respetando
    los párrafos, con SOLAPE_FRAGMENTO de traslape.

    POR QUÉ el solape: sin él, una idea que cae justo en el corte queda
    partida y ninguno de los dos fragmentos la responde completa.
    """
    if not texto or not texto.strip():
        return []
    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    fragmentos, actual = [], ""
    for p in parrafos:
        # Un párrafo más largo que el fragmento se corta por tamaño.
        while len(p) > TAM_FRAGMENTO:
            corte = p.rfind(" ", 0, TAM_FRAGMENTO)
            corte = corte if corte > TAM_FRAGMENTO // 2 else TAM_FRAGMENTO
            if actual:
                fragmentos.append(actual.strip())
                actual = ""
            fragmentos.append(p[:corte].strip())
            p = p[max(0, corte - SOLAPE_FRAGMENTO):]
        if len(actual) + len(p) + 2 <= TAM_FRAGMENTO:
            actual = f"{actual}\n\n{p}" if actual else p
        else:
            if actual:
                fragmentos.append(actual.strip())
            cola = actual[-SOLAPE_FRAGMENTO:] if actual else ""
            actual = (cola + "\n\n" + p).strip() if cola else p
    if actual.strip():
        fragmentos.append(actual.strip())
    return [f for f in fragmentos if len(f) > 40]


# ════════════════════════════════════════════════════════════════════
# INDEXAR / ELIMINAR
# ════════════════════════════════════════════════════════════════════

def indexar_documento(nombre: str, datos: bytes, usuario: str,
                      nota: str = "") -> dict:
    """
    Indexa (o ACTUALIZA, si el nombre ya existe) un documento.

    Pasos, en este orden, para que un fallo no deje el índice a medias:
      1. extraer texto → si no hay texto, se rechaza y se explica;
      2. guardar el original en disco y en el bucket;
      3. reemplazar los fragmentos de ESE documento en el índice;
      4. actualizar el registro y subirlo con guarda.

    Devuelve un diccionario con el resultado para mostrarlo en pantalla.
    """
    nombre = Path(nombre).name.strip()
    res = extraer(nombre, datos)
    if not res.ok:
        return {"ok": False, "documento": nombre,
                "mensaje": res.aviso or "No se pudo extraer texto."}

    fragmentos = trocear(res.texto)
    if not fragmentos:
        return {"ok": False, "documento": nombre,
                "mensaje": "El texto extraído quedó vacío tras el troceo."}

    # 2. original a disco + nube (para poder reconstruir el índice)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (DOCS_DIR / nombre).write_bytes(datos)
    except Exception:
        pass
    subido = nube.subir_bytes(nube.clave_documento(nombre), datos)

    # 3. índice: fuera los fragmentos viejos de este documento, entran los nuevos
    df = leer_chunks()
    previos = int((df["documento"] == nombre).sum()) if not df.empty else 0
    df = df[df["documento"] != nombre] if not df.empty else df
    nuevos = pd.DataFrame({
        "documento": nombre,
        "orden": range(len(fragmentos)),
        "ubicacion": [_ubicacion(f) for f in fragmentos],
        "texto": fragmentos,
    })
    df = pd.concat([df, nuevos], ignore_index=True) if not df.empty else nuevos
    _guardar_chunks(df)

    # 4. registro
    registro = leer_registro()
    es_actualizacion = nombre in registro
    registro[nombre] = {
        "sha": sha_bytes(datos),
        "bytes": len(datos),
        "fragmentos": len(fragmentos),
        "paginas": res.paginas,
        "caracteres": len(res.texto),
        "aviso": res.aviso,
        "nota": nota.strip(),
        "usuario": usuario,
        "fecha": sello_ahora(),
        "en_nube": bool(subido),
    }
    msg_nube = guardar_registro(registro)

    return {
        "ok": True,
        "documento": nombre,
        "actualizado": es_actualizacion,
        "fragmentos": len(fragmentos),
        "fragmentos_previos": previos,
        "paginas": res.paginas,
        "aviso": res.aviso,
        "mensaje": ("Documento ACTUALIZADO (reemplazó la versión anterior)."
                    if es_actualizacion else "Documento agregado."),
        "nube": msg_nube if subido else "No se pudo subir el original a la nube.",
    }


def eliminar_documento(nombre: str) -> str:
    """
    Borra un documento del índice, del disco y del bucket.
    Es el único caso donde el registro puede quedar con MENOS entradas,
    por eso va con permitir_reduccion=True.
    """
    df = leer_chunks()
    if not df.empty:
        _guardar_chunks(df[df["documento"] != nombre].reset_index(drop=True))
    registro = leer_registro()
    registro.pop(nombre, None)
    msg = guardar_registro(registro, permitir_reduccion=True)
    try:
        (DOCS_DIR / nombre).unlink(missing_ok=True)
    except Exception:
        pass
    nube.eliminar(nube.clave_documento(nombre))
    return f"'{nombre}' eliminado. {msg}"


def reconstruir_indice(usuario: str = "sistema") -> list[dict]:
    """
    Vuelve a leer TODOS los originales y rearma el índice desde cero.
    Sirve cuando se cambia el tamaño del fragmento o cuando el parquet
    se corrompe. Baja primero de la nube lo que falte en disco.
    """
    nube.hidratar(forzar=True)
    resultados = []
    for ruta in sorted(DOCS_DIR.glob("*")):
        if ruta.name.startswith(".") or not ruta.is_file():
            continue
        try:
            resultados.append(indexar_documento(ruta.name, ruta.read_bytes(), usuario))
        except Exception as e:
            resultados.append({"ok": False, "documento": ruta.name,
                               "mensaje": f"Error al reindexar: {e}"})
    return resultados


# ════════════════════════════════════════════════════════════════════
# BÚSQUEDA BM25
# ════════════════════════════════════════════════════════════════════
# BM25 con los parámetros clásicos. k1 controla cuánto suma repetir un
# término (satura: la quinta aparición aporta poco más que la cuarta);
# b, cuánto se penaliza un fragmento largo por ser largo.
K1 = 1.5
B = 0.75


def construir_bm25(df: pd.DataFrame) -> dict:
    """
    Prepara las estructuras de búsqueda. Se hace una vez y se cachea;
    no depende de la pregunta.
    """
    docs = [tokenizar(t) for t in df["texto"].tolist()] if not df.empty else []
    n = len(docs)
    largos = [len(d) for d in docs]
    largo_medio = (sum(largos) / n) if n else 0.0

    frec_doc: dict[str, int] = {}
    tablas = []
    for d in docs:
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        tablas.append(tf)
        for t in tf:
            frec_doc[t] = frec_doc.get(t, 0) + 1

    # idf de Robertson, con el +0.5 que evita valores negativos raros
    idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in frec_doc.items()}
    return {"n": n, "tf": tablas, "largos": largos,
            "largo_medio": largo_medio, "idf": idf}


def buscar(pregunta: str, k: int = 12,
           documentos: list[str] | None = None) -> pd.DataFrame:
    """
    Devuelve los k fragmentos más relevantes con su puntaje.

    'documentos' permite limitar la búsqueda a ciertos archivos (útil
    cuando el usuario quiere una respuesta basada solo en el Patmos, por
    ejemplo). Si la pregunta no tiene términos buscables, devuelve vacío
    en vez de inventar un orden.
    """
    df = leer_chunks()
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_CHUNKS + ["puntaje"])
    if documentos:
        df = df[df["documento"].isin(documentos)]
        if df.empty:
            return pd.DataFrame(columns=COLUMNAS_CHUNKS + ["puntaje"])
    df = df.reset_index(drop=True)

    idx = _bm25_cacheado(df)
    consulta = tokenizar(pregunta)
    if not consulta:
        return pd.DataFrame(columns=COLUMNAS_CHUNKS + ["puntaje"])

    from nucleo.util import normalizar
    frase = normalizar(pregunta).strip()
    # Largo medio con piso 1: un corpus recién creado puede dar 0 y la
    # división reventaría justo en la primera pregunta del usuario.
    largo_medio = idx["largo_medio"] or 1.0
    puntajes = []
    for i in range(idx["n"]):
        tf, largo = idx["tf"][i], idx["largos"][i]
        s = 0.0
        for t in consulta:
            f = tf.get(t, 0)
            if not f:
                continue
            denom = f + K1 * (1 - B + B * (largo / largo_medio))
            s += idx["idf"].get(t, 0.0) * (f * (K1 + 1)) / (denom or 1)
        # Bono por frase literal: si el fragmento contiene la pregunta tal
        # cual (o buena parte), casi siempre es el fragmento correcto.
        if len(frase) > 12 and frase in normalizar(df.at[i, "texto"]):
            s *= 1.5
        puntajes.append(s)

    df = df.assign(puntaje=puntajes)
    df = df[df["puntaje"] > 0].sort_values("puntaje", ascending=False).head(int(k))
    return df.reset_index(drop=True)


# El decorador se resuelve UNA vez, al importar el módulo. Definir la
# función cacheada dentro de otra función crearía un objeto nuevo en cada
# llamada y el caché nunca acertaría (el índice se recalcularía siempre).
try:                                        # pragma: no cover
    import streamlit as _st
    _cachear = _st.cache_resource(show_spinner=False)
except Exception:                           # pragma: no cover
    def _cachear(fn):
        return fn


@_cachear
def _construir_cacheado(_clave: tuple, textos: tuple) -> dict:
    """_clave (filas, caracteres) entra solo para invalidar el caché."""
    return construir_bm25(pd.DataFrame({"texto": list(textos)}))


def _bm25_cacheado(df: pd.DataFrame) -> dict:
    """
    Índice BM25 cacheado por la FORMA del corpus (filas + caracteres):
    si cambia un documento cambia la clave y se recalcula solo.
    """
    clave = (len(df), int(df["texto"].str.len().sum()))
    try:
        return _construir_cacheado(clave, tuple(df["texto"].tolist()))
    except Exception:
        return construir_bm25(df)


# ════════════════════════════════════════════════════════════════════
# RESUMEN PARA PANTALLA
# ════════════════════════════════════════════════════════════════════

def resumen_estado() -> dict:
    """Cifras del índice para el encabezado de carga y el sidebar."""
    registro = leer_registro()
    df = leer_chunks()
    ultima = max((v.get("fecha", "") for v in registro.values()), default="")
    return {
        "documentos": len(registro),
        "fragmentos": int(len(df)),
        "ultima_carga": ultima,
        "caracteres": int(sum(v.get("caracteres", 0) for v in registro.values())),
    }
