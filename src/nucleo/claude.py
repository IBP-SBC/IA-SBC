"""
nucleo/claude.py
================
La conversación con el modelo. Este módulo NO dibuja nada: arma el
prompt, llama a la API y devuelve texto. La vista se encarga del resto
(app/ no calcula, nucleo/ no dibuja).

POR QUÉ requests Y NO EL SDK 'anthropic'
----------------------------------------
El SDK oficial pasó a 1.0 en agosto de 2026 con cambios que rompen
(cambió la librería HTTP interna, subió el mínimo de Python y volvió
error enviar 'temperature'). Ya hablamos con Supabase por su API REST
usando requests: hacer lo mismo con la API de Claude nos deja con UNA
dependencia menos, sin sorpresas el día que salga la 2.0, y con el
código a la vista. Son ~50 líneas y se entienden de una lectura.

TRES DECISIONES QUE IMPORTAN
1. El CONTEXTO viaja marcado. Cada fragmento entra con la etiqueta
   [F1] Documento · ubicación, y las instrucciones piden citar con ese
   nombre. Así el usuario puede ir al documento y verificar. Sin
   trazabilidad, la respuesta es una opinión bonita.
2. NO se envía 'temperature'. En los modelos 5 cualquier valor distinto
   del defecto devuelve error 400.
3. Cuando la búsqueda no encuentra NADA, no se llama al modelo fingiendo
   que sí hay respaldo: se le dice explícitamente que no lo hay.
"""
from __future__ import annotations

import json

import pandas as pd

try:
    import requests
except Exception:                       # pragma: no cover
    requests = None

from nucleo.config import (
    MAX_CARACTERES_CONTEXTO,
    MAX_TOKENS_RESPUESTA,
    MODELO_DEFECTO,
)
from nucleo.instrucciones import leer_instrucciones

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"      # versión del contrato de la API, no del modelo
TIMEOUT_API = 180               # una respuesta larga puede tardar

# Reglas de la casa: van SIEMPRE, aunque alguien edite main.md. Son las
# que sostienen la confianza en la herramienta.
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
    """
    Arma el texto de contexto y devuelve las etiquetas usadas, en orden.

    Corta en MAX_CARACTERES_CONTEXTO: mejor 10 fragmentos completos que
    30 cortados por la mitad.
    """
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
# LLAVE Y LLAMADA
# ════════════════════════════════════════════════════════════════════

def _llave() -> tuple[str, str]:
    """
    Llave de la API desde los Secrets de Streamlit (o del entorno, para
    pruebas locales). NUNCA en el repositorio. Devuelve (llave, error).
    """
    clave = ""
    try:
        import streamlit as st
        if "anthropic" in st.secrets:
            clave = str(st.secrets["anthropic"].get("api_key", "")).strip()
        if not clave:
            clave = str(st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
    except Exception:
        clave = ""
    if not clave:
        import os
        clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        return "", ('Falta la llave de la API. Agregá en los Secrets de '
                    'Streamlit:\n\n[anthropic]\napi_key = "sk-ant-..."')
    return clave, ""


def api_lista() -> tuple[bool, str]:
    """Diagnóstico para pantalla: ¿está todo listo para conversar?"""
    if requests is None:
        return False, "Falta la librería 'requests' en el entorno."
    _clave, err = _llave()
    return (False, err) if err else (True, "Llave de API configurada.")


def _mensaje_de_error(status: int, cuerpo: str) -> str:
    """Traduce el código HTTP a algo accionable, no a un stack trace."""
    if status in (401, 403):
        return "⚠️ La llave de la API no es válida o fue revocada."
    if status == 404:
        return ("⚠️ El modelo pedido no está disponible para esta cuenta. "
                "Probá con otro en el selector del sidebar.")
    if status == 429:
        return ("⚠️ La API está limitando las peticiones (429). Esperá unos "
                "segundos y volvé a intentar.")
    if status == 400 and "credit" in cuerpo.lower():
        return "⚠️ La cuenta no tiene saldo disponible en la API."
    return f"⚠️ La API respondió {status}: {cuerpo[:300]}"


def responder_streaming(pregunta: str, historial: list[dict],
                        fragmentos: pd.DataFrame,
                        modelo: str = MODELO_DEFECTO):
    """
    Generador que entrega la respuesta por pedazos, para que el usuario
    vea avanzar el texto en vez de un spinner mudo.

    'historial' son los turnos previos [{'role','content'}] SIN el turno
    nuevo: la API no tiene memoria, se manda todo en cada llamada.
    """
    if requests is None:
        yield "⚠️ Falta la librería 'requests' en el entorno."
        return
    clave, err = _llave()
    if err:
        yield f"⚠️ {err}"
        return

    mensajes = [{"role": m["role"], "content": m["content"]}
                for m in historial[-10:]          # últimos 5 pares
                if m.get("role") in ("user", "assistant") and m.get("content")]
    mensajes.append({"role": "user", "content": pregunta})

    cuerpo = {
        "model": modelo,
        "max_tokens": MAX_TOKENS_RESPUESTA,
        "system": construir_system(fragmentos),
        "messages": mensajes,
        "stream": True,
    }
    cabeceras = {
        "x-api-key": clave,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }

    try:
        with requests.post(API_URL, headers=cabeceras, json=cuerpo,
                           stream=True, timeout=TIMEOUT_API) as r:
            if r.status_code != 200:
                yield _mensaje_de_error(r.status_code, r.text)
                return
            # Protocolo SSE: líneas 'data: {json}'. Solo nos interesan los
            # deltas de TEXTO; si el modelo razona antes de responder, esos
            # bloques no se muestran porque no son la respuesta.
            for linea in r.iter_lines(decode_unicode=True):
                if not linea or not linea.startswith("data:"):
                    continue
                dato = linea[5:].strip()
                if dato == "[DONE]":
                    break
                try:
                    ev = json.loads(dato)
                except Exception:
                    continue
                tipo = ev.get("type")
                if tipo == "content_block_delta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")
                elif tipo == "error":
                    detalle = ev.get("error", {}).get("message", "sin detalle")
                    yield f"\n\n⚠️ Error de la API: {detalle}"
                    return
    except requests.exceptions.Timeout:
        yield ("⚠️ La respuesta tardó demasiado y se cortó. Probá con una "
               "pregunta más específica o con menos fragmentos.")
    except Exception as e:
        yield f"⚠️ Falló la llamada al modelo: {e}"


def titulo_de_conversacion(pregunta: str) -> str:
    """Título corto para identificar una conversación, sin llamar al modelo."""
    t = " ".join(str(pregunta).split())
    return (t[:48] + "…") if len(t) > 48 else t
