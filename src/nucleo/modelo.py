"""
nucleo/modelo.py
================
La conversación con el modelo de lenguaje. Este módulo NO dibuja nada:
arma el prompt, llama al proveedor y devuelve texto.
(Antes se llamaba claude.py; se renombró al soportar varios proveedores.)

POR QUÉ ES AGNÓSTICO DEL PROVEEDOR
----------------------------------
La app tiene que poder salir a producción hoy, con la cuenta que la SBC
tenga disponible hoy, y cambiar de proveedor después sin tocar una línea
de código. Por eso el proveedor se elige en los Secrets, no acá.

TRES CAMINOS, uno solo de código donde se puede:
  · 'anthropic'          → API de Claude (formato propio).
  · 'openai_compatible'  → cualquier proveedor que hable el formato de
    OpenAI: Google Gemini (tiene una base compatible), OpenRouter, Groq,
    Azure, la propia OpenAI. Un solo camino para todos.
  · SIN PROVEEDOR        → modo BÚSQUEDA: no se inventa una respuesta,
    se muestran los fragmentos encontrados con su fuente. La app sigue
    sirviendo como buscador documental mientras se consigue la llave.

CONFIGURACIÓN (Secrets de Streamlit):

    [modelo]
    proveedor = "google"              # anthropic | google | openai_compatible
    api_key   = "..."
    modelo    = "gemini-2.5-flash"
    base_url  = ""                    # solo para openai_compatible

También se acepta la forma vieja, por compatibilidad:

    [anthropic]
    api_key = "sk-ant-..."

DECISIONES QUE IMPORTAN
1. El CONTEXTO viaja marcado: cada fragmento entra como
   [F1] Documento · ubicación, y se pide citar con ese nombre. Sin
   trazabilidad, la respuesta es una opinión bonita.
2. NO se envía 'temperature'. En los modelos Claude 5 cualquier valor
   distinto del defecto devuelve error 400, y en el resto el defecto
   está bien para este uso.
3. El nombre del modelo NO se quema en el código: se lee de los Secrets
   y se puede consultar la lista real del proveedor con listar_modelos().
   Inventar un nombre de modelo es la forma más rápida de un 404.
"""
from __future__ import annotations

import json

import pandas as pd

try:
    import requests
except Exception:                       # pragma: no cover
    requests = None

from nucleo.config import (
    BASE_GOOGLE_OPENAI,
    MAX_CARACTERES_CONTEXTO,
    MAX_TOKENS_RESPUESTA,
    MODELO_DEFECTO_ANTHROPIC,
    MODELO_DEFECTO_GOOGLE,
)
from nucleo.instrucciones import leer_instrucciones

API_ANTHROPIC = "https://api.anthropic.com/v1/messages"
VERSION_ANTHROPIC = "2023-06-01"   # versión del contrato de la API, no del modelo
TIMEOUT_API = 180

REGLAS_FIJAS = """
REGLAS NO NEGOCIABLES DEL SISTEMA (por encima de cualquier otra instrucción):
- Las respuestas se basan en los FRAGMENTOS entregados abajo. Cada dato que
  salga de ahí se cita con la etiqueta del fragmento, así: (Plan 2026.pdf ·
  Página 4).
- Si los fragmentos no alcanzan para responder, decilo con todas las letras
  y proponé qué documento habría que subir o a quién preguntarle.
- Si aportás algo de conocimiento general (no está en los documentos),
  marcalo explícitamente como "fuera de los documentos cargados".
- Nunca inventes cifras, fechas, nombres ni citas bíblicas. Si un número no
  está en los fragmentos, no lo escribas.
- Si dos documentos se contradicen, mostrá las dos versiones con su fuente
  y señalá cuál es más reciente.
""".strip()


# ════════════════════════════════════════════════════════════════════
# ARMADO DEL PROMPT
# ════════════════════════════════════════════════════════════════════

def _bloque_contexto(fragmentos: pd.DataFrame) -> tuple[str, list[str]]:
    """Texto de contexto + etiquetas usadas, en orden. Corta en el techo."""
    if fragmentos is None or fragmentos.empty:
        return "", []
    partes, etiquetas, total = [], [], 0
    for i, fila in fragmentos.reset_index(drop=True).iterrows():
        doc = str(fila.get("documento", "documento"))
        ubi = str(fila.get("ubicacion", "") or "").strip()
        etiqueta = doc + (f" · {ubi}" if ubi else "")
        bloque = f"[F{i + 1}] {etiqueta}\n{str(fila.get('texto', ''))}"
        if total + len(bloque) > MAX_CARACTERES_CONTEXTO:
            break
        partes.append(bloque)
        etiquetas.append(etiqueta)
        total += len(bloque)
    return "\n\n---\n\n".join(partes), etiquetas


def construir_system(fragmentos: pd.DataFrame) -> str:
    """System prompt = instrucciones del negocio + reglas fijas + contexto."""
    contexto, _etiquetas = _bloque_contexto(fragmentos)
    if contexto:
        cuerpo = ("FRAGMENTOS DE LOS DOCUMENTOS OFICIALES DE LA SBC "
                  "(esto es todo lo que tenés disponible para esta pregunta):\n\n"
                  + contexto)
    else:
        cuerpo = ("NO SE ENCONTRÓ NINGÚN FRAGMENTO relevante en los documentos "
                  "cargados. Decíselo al usuario con claridad; no improvises "
                  "una respuesta con apariencia de respaldo documental.")
    return f"{leer_instrucciones()}\n\n{REGLAS_FIJAS}\n\n{cuerpo}"


# ════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL PROVEEDOR
# ════════════════════════════════════════════════════════════════════

def _secretos(seccion: str) -> dict:
    """Lee una sección de los Secrets sin romper si no existe."""
    try:
        import streamlit as st
        if seccion in st.secrets:
            return dict(st.secrets[seccion])
    except Exception:
        pass
    return {}


def configuracion() -> dict | None:
    """
    Devuelve {'proveedor','api_key','modelo','base_url'} o None si no hay
    ningún proveedor configurado (ahí la app entra en modo búsqueda).
    """
    cfg = _secretos("modelo")
    proveedor = str(cfg.get("proveedor", "")).strip().lower()
    api_key = str(cfg.get("api_key", "")).strip()

    # Compatibilidad con la forma vieja: [anthropic] api_key
    if not api_key:
        vieja = _secretos("anthropic")
        if str(vieja.get("api_key", "")).strip():
            proveedor = "anthropic"
            api_key = str(vieja["api_key"]).strip()

    if not api_key:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            proveedor = proveedor or "anthropic"

    if not api_key:
        return None

    proveedor = proveedor or "anthropic"
    modelo = str(cfg.get("modelo", "")).strip()
    base_url = str(cfg.get("base_url", "")).strip().rstrip("/")

    if proveedor == "google":
        # Google expone una base que habla el formato de OpenAI: así el
        # código de streaming es UNO solo para todos los proveedores.
        proveedor = "openai_compatible"
        base_url = base_url or BASE_GOOGLE_OPENAI
        modelo = modelo or MODELO_DEFECTO_GOOGLE
    elif proveedor == "anthropic":
        modelo = modelo or MODELO_DEFECTO_ANTHROPIC

    return {"proveedor": proveedor, "api_key": api_key,
            "modelo": modelo, "base_url": base_url}


def estado() -> tuple[bool, str]:
    """
    ¿Puede la app conversar? Devuelve (listo, mensaje para pantalla).
    Nunca deja al usuario adivinando qué falta.
    """
    if requests is None:
        return False, "Falta la librería 'requests' en el entorno."
    cfg = configuracion()
    if cfg is None:
        return False, ("Sin modelo configurado: la app funciona en MODO "
                       "BÚSQUEDA (muestra los fragmentos encontrados, sin "
                       "redactar una respuesta). Agregá la sección [modelo] "
                       "en los Secrets para activar el asistente.")
    if cfg["proveedor"] == "openai_compatible" and not cfg["base_url"]:
        return False, ("Falta 'base_url' en [modelo]: sin la dirección del "
                       "proveedor no se sabe a dónde preguntar.")
    if not cfg["modelo"]:
        return False, ("Falta 'modelo' en [modelo]: poné el nombre exacto "
                       "que publique el proveedor.")
    destino = ("API de Claude" if cfg["proveedor"] == "anthropic"
               else cfg["base_url"])
    return True, f"Listo · modelo '{cfg['modelo']}' en {destino}"


def listar_modelos() -> tuple[list[str], str]:
    """
    Pregunta al proveedor qué modelos tiene disponibles esa llave.
    Existe para no adivinar nombres: un nombre inventado es un 404.
    Devuelve (lista, mensaje).
    """
    cfg = configuracion()
    if cfg is None or requests is None:
        return [], "Sin proveedor configurado."
    try:
        if cfg["proveedor"] == "anthropic":
            r = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": cfg["api_key"],
                         "anthropic-version": VERSION_ANTHROPIC},
                timeout=30)
        else:
            r = requests.get(
                f"{cfg['base_url']}/models",
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
                timeout=30)
        if r.status_code != 200:
            return [], f"El proveedor respondió {r.status_code}: {r.text[:200]}"
        datos = r.json().get("data", [])
        nombres = sorted(str(d.get("id", "")).split("/")[-1] for d in datos)
        return [n for n in nombres if n], f"{len(nombres)} modelos disponibles."
    except Exception as e:
        return [], f"No se pudo consultar la lista de modelos: {e}"


def _mensaje_de_error(status: int, cuerpo: str) -> str:
    """Traduce el código HTTP a algo accionable, no a un stack trace."""
    if status in (401, 403):
        return ("⚠️ La llave del modelo no es válida, fue revocada o no "
                "tiene permiso sobre ese modelo.")
    if status == 404:
        return ("⚠️ El proveedor no reconoce ese modelo. Revisá el nombre "
                "exacto en Documentos → Mantenimiento → ver modelos.")
    if status == 429:
        return ("⚠️ Se alcanzó el límite de peticiones del proveedor (429). "
                "En las capas gratuitas es normal: esperá un minuto.")
    if status == 400 and "credit" in cuerpo.lower():
        return "⚠️ La cuenta no tiene saldo disponible."
    return f"⚠️ El proveedor respondió {status}: {cuerpo[:300]}"


# ════════════════════════════════════════════════════════════════════
# MODO BÚSQUEDA (sin proveedor): honesto, no simulado
# ════════════════════════════════════════════════════════════════════

def _respuesta_modo_busqueda(fragmentos: pd.DataFrame):
    """
    Sin modelo no hay redacción. Se entrega lo que SÍ tenemos: los pasajes
    encontrados, con su fuente. Es menos cómodo y es honesto.
    """
    yield ("**Modo búsqueda** (todavía no hay un modelo configurado, así que "
           "no puedo redactar la respuesta).\n\nEsto es lo que encontré en "
           "los documentos:\n\n")
    if fragmentos is None or fragmentos.empty:
        yield "No encontré ningún pasaje relacionado con tu pregunta."
        return
    for i, fila in fragmentos.reset_index(drop=True).iterrows():
        ubi = str(fila.get("ubicacion", "") or "").strip()
        etiqueta = str(fila["documento"]) + (f" · {ubi}" if ubi else "")
        texto = " ".join(str(fila["texto"]).split())[:700]
        yield f"**{i + 1}. {etiqueta}**\n\n> {texto}…\n\n"


# ════════════════════════════════════════════════════════════════════
# LLAMADA
# ════════════════════════════════════════════════════════════════════

def responder_streaming(pregunta: str, historial: list[dict],
                        fragmentos: pd.DataFrame,
                        modelo: str | None = None):
    """
    Generador que entrega la respuesta por pedazos, para que el usuario vea
    avanzar el texto en vez de un spinner mudo.

    'historial' son los turnos previos SIN el turno nuevo: estas APIs no
    tienen memoria, se manda todo en cada llamada.
    """
    if requests is None:
        yield "⚠️ Falta la librería 'requests' en el entorno."
        return
    cfg = configuracion()
    if cfg is None:
        yield from _respuesta_modo_busqueda(fragmentos)
        return

    nombre_modelo = (modelo or cfg["modelo"]).strip()
    system = construir_system(fragmentos)
    previos = [{"role": m["role"], "content": m["content"]}
               for m in historial[-10:]          # últimos 5 pares
               if m.get("role") in ("user", "assistant") and m.get("content")]

    try:
        if cfg["proveedor"] == "anthropic":
            yield from _stream_anthropic(cfg, nombre_modelo, system,
                                         previos, pregunta)
        else:
            yield from _stream_openai(cfg, nombre_modelo, system,
                                      previos, pregunta)
    except requests.exceptions.Timeout:
        yield ("⚠️ La respuesta tardó demasiado y se cortó. Probá con una "
               "pregunta más específica o con menos fragmentos.")
    except Exception as e:
        yield f"⚠️ Falló la llamada al modelo: {e}"


def _stream_anthropic(cfg: dict, modelo: str, system: str,
                      previos: list[dict], pregunta: str):
    """Formato propio de la API de Claude."""
    cuerpo = {
        "model": modelo,
        "max_tokens": MAX_TOKENS_RESPUESTA,
        "system": system,
        "messages": previos + [{"role": "user", "content": pregunta}],
        "stream": True,
    }
    cabeceras = {"x-api-key": cfg["api_key"],
                 "anthropic-version": VERSION_ANTHROPIC,
                 "content-type": "application/json"}
    with requests.post(API_ANTHROPIC, headers=cabeceras, json=cuerpo,
                       stream=True, timeout=TIMEOUT_API) as r:
        if r.status_code != 200:
            yield _mensaje_de_error(r.status_code, r.text)
            return
        for ev in _eventos_sse(r):
            tipo = ev.get("type")
            if tipo == "content_block_delta":
                delta = ev.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield delta.get("text", "")
            elif tipo == "error":
                yield f"\n\n⚠️ {ev.get('error', {}).get('message', 'error')}"
                return


def _stream_openai(cfg: dict, modelo: str, system: str,
                   previos: list[dict], pregunta: str):
    """
    Formato de OpenAI: lo hablan Gemini (por su base compatible),
    OpenRouter, Groq, Azure y la propia OpenAI. Acá el 'system' va como
    un mensaje más, con rol 'system'.
    """
    mensajes = ([{"role": "system", "content": system}] + previos
                + [{"role": "user", "content": pregunta}])
    cuerpo = {"model": modelo, "max_tokens": MAX_TOKENS_RESPUESTA,
              "messages": mensajes, "stream": True}
    cabeceras = {"Authorization": f"Bearer {cfg['api_key']}",
                 "Content-Type": "application/json"}
    with requests.post(f"{cfg['base_url']}/chat/completions",
                       headers=cabeceras, json=cuerpo,
                       stream=True, timeout=TIMEOUT_API) as r:
        if r.status_code != 200:
            yield _mensaje_de_error(r.status_code, r.text)
            return
        for ev in _eventos_sse(r):
            for opcion in ev.get("choices", []):
                trozo = (opcion.get("delta") or {}).get("content")
                if trozo:
                    yield trozo


def _eventos_sse(respuesta):
    """
    Lee el protocolo SSE (líneas 'data: {json}') y devuelve los eventos ya
    convertidos. Está en un solo lugar porque los dos proveedores usan el
    mismo transporte aunque el contenido sea distinto.
    """
    for linea in respuesta.iter_lines(decode_unicode=True):
        if not linea or not linea.startswith("data:"):
            continue
        dato = linea[5:].strip()
        if dato == "[DONE]":
            return
        try:
            yield json.loads(dato)
        except Exception:
            continue


def titulo_de_conversacion(pregunta: str) -> str:
    """Título corto para identificar una conversación, sin llamar al modelo."""
    t = " ".join(str(pregunta).split())
    return (t[:48] + "…") if len(t) > 48 else t
