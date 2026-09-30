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
from nucleo import nube
from nucleo.instrucciones import leer_instrucciones

# Archivo de estado donde se guarda el modelo elegido desde la app. Vive
# en el bucket, así sobrevive al reinicio y no obliga a editar los Secrets
# (que exigen redesplegar y que solo puede tocar quien tenga esa cuenta).
ARCHIVO_MODELO = "modelo_activo.json"

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

    # El modelo elegido DESDE LA APP manda sobre el de los Secrets: es el
    # que se puede corregir en caliente cuando el proveedor renombra o
    # retira un modelo, sin esperar un despliegue.
    elegido = leer_modelo_activo()
    if elegido:
        modelo = elegido

    return {"proveedor": proveedor, "api_key": api_key,
            "modelo": modelo, "base_url": base_url}


# ── Modelo elegido desde la app (override persistente) ───────────────

def leer_modelo_activo() -> str:
    """Nombre del modelo guardado desde Mantenimiento. '' si no hay."""
    try:
        import streamlit as st
        if "_modelo_activo" in st.session_state:
            return str(st.session_state["_modelo_activo"] or "")
    except Exception:
        st = None
    datos = nube.leer_json_remoto(ARCHIVO_MODELO) or {}
    nombre = str(datos.get("modelo", "") or "")
    try:
        if st is not None:
            st.session_state["_modelo_activo"] = nombre
    except Exception:
        pass
    return nombre


def guardar_modelo_activo(nombre: str, usuario: str) -> str:
    """Guarda el modelo elegido. Devuelve un mensaje para pantalla."""
    nombre = (nombre or "").strip()
    from nucleo.util import sello_ahora
    datos = {"modelo": nombre, "usuario": usuario, "fecha": sello_ahora()}
    ok = nube.subir_bytes(nube.clave_estado(ARCHIVO_MODELO),
                          json.dumps(datos, ensure_ascii=False).encode("utf-8"))
    try:
        import streamlit as st
        st.session_state["_modelo_activo"] = nombre
    except Exception:
        pass
    if not nube.nube_activa():
        return (f"Modelo '{nombre}' activo en esta sesión. Sin nube "
                "configurada, se pierde al reiniciar.")
    return (f"Modelo '{nombre}' guardado." if ok
            else f"Modelo '{nombre}' activo, pero NO se pudo guardar en la nube.")


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
        nombres = sorted({str(d.get("id", "")).split("/")[-1] for d in datos})
        nombres = [n for n in nombres if n]
        return nombres, f"{len(nombres)} modelos disponibles."
    except Exception as e:
        return [], f"No se pudo consultar la lista de modelos: {e}"


# Palabras que delatan un modelo que NO sirve para conversar. La lista de
# Google trae 58 entradas y la mayoría son de imagen, audio, video,
# traducción o embeddings: ofrecerlas todas es hacer que el usuario elija
# mal y después ver un 404 que parece un error de la app.
_NO_CONVERSAN = ("embedding", "tts", "image", "audio", "video", "veo",
                 "lyria", "nano-banana", "transcribe", "translate", "live",
                 "robotics", "computer-use", "aqa", "deep-research")


def modelos_para_conversar(nombres: list[str]) -> list[str]:
    """Filtra la lista del proveedor dejando los que sirven para chat."""
    return [n for n in nombres
            if not any(p in n.lower() for p in _NO_CONVERSAN)]


def probar_modelo(nombre: str) -> tuple[bool, str]:
    """
    Hace una llamada mínima y REAL al modelo, sin streaming, y devuelve
    exactamente lo que respondió el proveedor.

    Existe porque el listado de modelos no garantiza que un modelo atienda
    conversación: la única prueba de que sirve es preguntarle.
    """
    cfg = configuracion()
    if cfg is None or requests is None:
        return False, "Sin proveedor configurado."
    nombre = (nombre or cfg["modelo"]).strip()
    prueba = [{"role": "user", "content": "Respondé solo con la palabra: listo"}]
    try:
        if cfg["proveedor"] == "anthropic":
            r = requests.post(
                API_ANTHROPIC,
                headers={"x-api-key": cfg["api_key"],
                         "anthropic-version": VERSION_ANTHROPIC,
                         "content-type": "application/json"},
                json={"model": nombre, "max_tokens": 20, "messages": prueba},
                timeout=60)
        else:
            r = requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}",
                         "Content-Type": "application/json"},
                json={"model": nombre, "max_tokens": 20, "messages": prueba},
                timeout=60)
    except Exception as e:
        return False, f"No se pudo llegar al proveedor: {e}"
    if r.status_code == 200:
        return True, f"'{nombre}' responde correctamente."
    return False, _mensaje_de_error(r.status_code, r.text)


def _detalle_del_proveedor(cuerpo: str) -> str:
    """
    Saca el mensaje que realmente mandó el proveedor. Los dos formatos que
    usamos lo traen en {'error': {'message': ...}}; si no se puede leer, se
    devuelve el texto crudo recortado. NUNCA se descarta: el detalle es lo
    único que permite diagnosticar.
    """
    try:
        datos = json.loads(cuerpo)
        error = datos.get("error", datos)
        if isinstance(error, dict):
            for clave in ("message", "detail", "status"):
                if error.get(clave):
                    return str(error[clave])[:400]
    except Exception:
        pass
    return " ".join(str(cuerpo).split())[:400]


def _mensaje_de_error(status: int, cuerpo: str) -> str:
    """
    Traduce el código HTTP a algo accionable Y muestra lo que dijo el
    proveedor.

    Este detalle faltaba hasta la v1.1.0: ante un 404 la app decía "no
    reconoce ese modelo" aunque el modelo estuviera en la lista, y el
    mensaje real del proveedor —el que decía qué pasaba de verdad— se
    tiraba a la basura. Un error maquillado es peor que un error crudo.
    """
    detalle = _detalle_del_proveedor(cuerpo)
    if status in (401, 403):
        pista = ("La llave no es válida, fue revocada o no tiene permiso "
                 "sobre ese modelo.")
    elif status == 404:
        pista = ("El proveedor no atendió la petición para ese modelo. Puede "
                 "ser el nombre, o que ese modelo no acepte conversación "
                 "(los de imagen, audio, video o embeddings no sirven). "
                 "Probalo en Documentos → Mantenimiento → Probar modelo.")
    elif status == 429:
        pista = ("Se alcanzó el límite de peticiones del proveedor. En las "
                 "capas gratuitas es normal: esperá un minuto.")
    elif status == 400 and "credit" in cuerpo.lower():
        pista = "La cuenta no tiene saldo disponible."
    else:
        pista = "El proveedor rechazó la petición."
    return f"⚠️ **{status}** · {pista}\n\n> Dijo el proveedor: {detalle}"


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

def turnos_validos(historial: list[dict], maximo: int = 10) -> list[dict]:
    """
    Deja solo los turnos que se le pueden mandar al proveedor.

    Descarta los vacíos: un turno sin contenido deja dos mensajes del
    mismo rol seguidos y el proveedor puede rechazar la conversación
    entera desde ahí. Eso explica el caso real de "no respondió hasta que
    reinicié la app": una respuesta vacía quedaba en el historial y
    envenenaba todas las preguntas siguientes de esa sesión.
    """
    return [{"role": m["role"], "content": m["content"]}
            for m in (historial or [])[-maximo:]
            if m.get("role") in ("user", "assistant")
            and str(m.get("content", "")).strip()]


def mensaje_respuesta_vacia(motivo: str) -> str:
    """Explica en palabras por qué el modelo no escribió nada."""
    pista = {
        "length": ("se quedó sin presupuesto de tokens antes de escribir "
                   "(suele pasar cuando razona mucho antes de responder)"),
        "max_tokens": "se quedó sin presupuesto de tokens antes de escribir",
        "MAX_TOKENS": "se quedó sin presupuesto de tokens antes de escribir",
        "content_filter": "el proveedor bloqueó la respuesta por sus filtros",
        "SAFETY": "el proveedor bloqueó la respuesta por sus filtros",
    }.get(str(motivo), f"el proveedor cerró la respuesta con el motivo '{motivo}'")
    return (f"⚠️ **El modelo no devolvió texto** en dos intentos: {pista}.\n\n"
            "Qué hacer: preguntá algo más acotado, bajá el número de "
            "fragmentos en el panel de la izquierda, o probá otro modelo en "
            "Documentos → Mantenimiento.")


def responder_streaming(pregunta: str, historial: list[dict],
                        fragmentos: pd.DataFrame,
                        modelo: str | None = None,
                        diagnostico: dict | None = None):
    """
    Generador que entrega la respuesta por pedazos, para que el usuario vea
    avanzar el texto en vez de un spinner mudo.

    'historial' son los turnos previos SIN el turno nuevo: estas APIs no
    tienen memoria, se manda todo en cada llamada.

    'diagnostico' es un diccionario opcional donde se anotan modelo,
    tamaño del envío, duración, motivo de fin e intentos. La vista lo
    muestra en un desplegable. Sirve para que "no respondió" deje de ser
    un misterio.

    POR QUÉ HAY UN REINTENTO (uno solo):
    pasó en producción que una pregunta no obtuvo respuesta y la MISMA
    pregunta funcionó después de reiniciar. Un stream puede terminar sin
    una sola letra de texto: el modelo gasta todo su presupuesto de tokens
    razonando antes de escribir, o el proveedor corta la conexión a mitad
    de camino. Antes eso dejaba el chat MUDO, que es la peor forma de
    fallar: el usuario no sabe si preguntar de nuevo, esperar o si la app
    está rota. Ahora se reintenta una vez con el doble de presupuesto y,
    si vuelve vacío, se explica qué pasó.
    """
    import time

    diag = diagnostico if isinstance(diagnostico, dict) else {}
    diag.clear()

    if requests is None:
        yield "⚠️ Falta la librería 'requests' en el entorno."
        return
    cfg = configuracion()
    if cfg is None:
        diag["modo"] = "búsqueda (sin proveedor configurado)"
        yield from _respuesta_modo_busqueda(fragmentos)
        return

    nombre_modelo = (modelo or cfg["modelo"]).strip()
    system = construir_system(fragmentos)

    previos = turnos_validos(historial)   # sin turnos vacíos (ver arriba)

    diag.update({
        "modelo": nombre_modelo,
        "proveedor": cfg["proveedor"],
        "fragmentos": 0 if fragmentos is None else int(len(fragmentos)),
        "caracteres_enviados": len(system) + sum(len(m["content"]) for m in previos),
        "turnos_previos": len(previos),
    })

    inicio = time.time()
    for intento in (1, 2):
        presupuesto = MAX_TOKENS_RESPUESTA * intento   # el reintento pide el doble
        recibido = 0
        fin = {}
        try:
            if cfg["proveedor"] == "anthropic":
                flujo = _stream_anthropic(cfg, nombre_modelo, system,
                                          previos, pregunta, presupuesto, fin)
            else:
                flujo = _stream_openai(cfg, nombre_modelo, system,
                                       previos, pregunta, presupuesto, fin)
            for trozo in flujo:
                recibido += len(trozo)
                yield trozo
        except requests.exceptions.Timeout:
            diag.update({"intentos": intento, "motivo_fin": "timeout",
                         "segundos": round(time.time() - inicio, 1)})
            yield ("⚠️ La respuesta tardó demasiado y se cortó. Probá con una "
                   "pregunta más específica o bajá los fragmentos que reviso.")
            return
        except Exception as e:
            diag.update({"intentos": intento, "motivo_fin": f"excepción: {e}",
                         "segundos": round(time.time() - inicio, 1)})
            yield f"⚠️ Falló la llamada al modelo: {e}"
            return

        diag.update({"intentos": intento,
                     "motivo_fin": fin.get("motivo", "desconocido"),
                     "caracteres_recibidos": recibido,
                     "segundos": round(time.time() - inicio, 1)})

        if recibido > 0 or fin.get("error"):
            return          # hubo respuesta, o ya se mostró el error del proveedor

        if intento == 1:
            yield ("_El modelo terminó sin escribir nada. Reintentando una vez "
                   "con más espacio para la respuesta…_\n\n")

    # Segundo intento también vacío: se explica, no se deja mudo.
    yield mensaje_respuesta_vacia(diag.get("motivo_fin", "desconocido"))


def _stream_anthropic(cfg: dict, modelo: str, system: str,
                      previos: list[dict], pregunta: str,
                      presupuesto: int, fin: dict):
    """Formato propio de la API de Claude. Anota en 'fin' cómo terminó."""
    cuerpo = {
        "model": modelo,
        "max_tokens": presupuesto,
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
            fin["error"] = True
            fin["motivo"] = f"HTTP {r.status_code}"
            yield _mensaje_de_error(r.status_code, r.text)
            return
        for ev in _eventos_sse(r):
            tipo = ev.get("type")
            if tipo == "content_block_delta":
                delta = ev.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield delta.get("text", "")
            elif tipo == "message_delta":
                fin["motivo"] = ev.get("delta", {}).get("stop_reason") or fin.get("motivo")
            elif tipo == "error":
                fin["error"] = True
                yield f"\n\n⚠️ {ev.get('error', {}).get('message', 'error')}"
                return


def _stream_openai(cfg: dict, modelo: str, system: str,
                   previos: list[dict], pregunta: str,
                   presupuesto: int, fin: dict):
    """
    Formato de OpenAI: lo hablan Gemini (por su base compatible),
    OpenRouter, Groq, Azure y la propia OpenAI. Acá el 'system' va como
    un mensaje más, con rol 'system'.
    """
    mensajes = ([{"role": "system", "content": system}] + previos
                + [{"role": "user", "content": pregunta}])
    cuerpo = {"model": modelo, "max_tokens": presupuesto,
              "messages": mensajes, "stream": True}
    cabeceras = {"Authorization": f"Bearer {cfg['api_key']}",
                 "Content-Type": "application/json"}
    with requests.post(f"{cfg['base_url']}/chat/completions",
                       headers=cabeceras, json=cuerpo,
                       stream=True, timeout=TIMEOUT_API) as r:
        if r.status_code != 200:
            fin["error"] = True
            fin["motivo"] = f"HTTP {r.status_code}"
            yield _mensaje_de_error(r.status_code, r.text)
            return
        for ev in _eventos_sse(r):
            for opcion in ev.get("choices", []):
                trozo = (opcion.get("delta") or {}).get("content")
                if trozo:
                    yield trozo
                if opcion.get("finish_reason"):
                    fin["motivo"] = opcion["finish_reason"]


def _eventos_sse(respuesta):
    """
    Lee el protocolo SSE (líneas 'data: {json}') y devuelve los eventos ya
    convertidos. Está en un solo lugar porque los dos proveedores usan el
    mismo transporte aunque el contenido sea distinto.

    LA DECODIFICACIÓN SE HACE ACÁ, A MANO, EN UTF-8. Por qué:
    requests, cuando el servidor manda un tipo 'text/*' SIN declarar el
    juego de caracteres, asume ISO-8859-1 (una regla vieja de HTTP). El
    stream viene en UTF-8, así que las tildes y las eñes llegaban rotas:
    "Activo-Público" se veía "Activo-PÃºblico". Y si requests no resuelve
    ningún encoding, devuelve bytes: ahí ninguna línea empieza por "data:"
    y la respuesta sale VACÍA sin un solo error. El protocolo SSE define
    UTF-8, así que no hay nada que adivinar.
    """
    for linea in respuesta.iter_lines(decode_unicode=False):
        if not linea:
            continue
        if isinstance(linea, bytes):
            linea = linea.decode("utf-8", errors="replace")
        if not linea.startswith("data:"):
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
