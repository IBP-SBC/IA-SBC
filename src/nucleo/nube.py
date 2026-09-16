"""
nucleo/nube.py
==============
Persistencia en Supabase Storage.

POR QUÉ: el disco de Streamlit Cloud es EFÍMERO. Tras un reboot la app
arranca con las carpetas vacías. Si no guardamos afuera, el equipo sube
los documentos hoy y mañana no están.

REGLAS OBLIGATORIAS (nacidas de tres pérdidas de datos reales en
sbc_ventas: accesos.json, cargas.json y produccion_movimientos.parquet):
  1. INTENTAR RECUPERAR de la nube antes de dar un archivo por inexistente.
  2. FUSIONAR con lo remoto antes de escribir. Nunca sobrescribir a ciegas.
  3. GUARDA AL SUBIR: no reemplazar un registro remoto por uno con MENOS
     documentos, salvo que sea un borrado explícito del usuario.
  4. Si algo se bloquea, DECIRLO EN PANTALLA. Nada falla en silencio.

Se habla con la API REST de Storage por requests: una dependencia menos
que el SDK y el mismo patrón que ya funciona en sbc_ventas.

CONFIGURACIÓN (Streamlit → Settings → Secrets):
    [supabase]
    url    = "https://xxxxxxxx.supabase.co"
    key    = "<service_role key>"
    bucket = "ia-sbc"
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except Exception:          # pragma: no cover
    requests = None        # sin requests la app funciona solo en local

from nucleo.config import (
    BUCKET_DEFECTO,
    DOCS_DIR,
    ESTADO_DIR,
    PREFIJO_DOCS,
    PREFIJO_ESTADO,
    TIMEOUT_NUBE,
)


# ════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════

def _config() -> dict | None:
    """
    Lee st.secrets['supabase']. Devuelve {'url','key','bucket'} o None.
    Nunca lanza excepción: sin nube, la app sigue en modo local.

    La URL se normaliza a esquema+dominio, porque es común pegar la del
    Data API ('https://xxx.supabase.co/rest/v1/') y entonces los
    endpoints de Storage quedarían mal formados.
    """
    if requests is None:
        return None
    try:
        import streamlit as st
        if "supabase" not in st.secrets:
            return None
        cfg = st.secrets["supabase"]
        url_raw = str(cfg.get("url", "")).strip()
        key = str(cfg.get("key", "")).strip()
        bucket = str(cfg.get("bucket", BUCKET_DEFECTO)).strip() or BUCKET_DEFECTO
        if not url_raw or not key:
            return None
        p = urlparse(url_raw if "//" in url_raw else "https://" + url_raw)
        url = f"{p.scheme}://{p.netloc}" if (p.scheme and p.netloc) else url_raw.rstrip("/")
        return {"url": url, "key": key, "bucket": bucket}
    except Exception:
        return None


def nube_activa() -> bool:
    """True si Supabase está configurado y utilizable."""
    return _config() is not None


def _headers(cfg: dict, extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {cfg['key']}", "apikey": cfg["key"]}
    if extra:
        h.update(extra)
    return h


# ════════════════════════════════════════════════════════════════════
# OPERACIONES BÁSICAS (devuelven bool/valor, nunca rompen la app)
# ════════════════════════════════════════════════════════════════════

def subir_bytes(clave: str, contenido: bytes) -> bool:
    """Sube contenido al bucket (crea o reemplaza). True si quedó."""
    cfg = _config()
    if cfg is None:
        return False
    try:
        url = f"{cfg['url']}/storage/v1/object/{cfg['bucket']}/{clave}"
        r = requests.post(
            url, data=contenido,
            headers=_headers(cfg, {
                "x-upsert": "true",
                "Content-Type": "application/octet-stream",
            }),
            timeout=TIMEOUT_NUBE,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def subir_archivo(ruta_local: str | Path, clave: str) -> bool:
    """Sube un archivo del disco al bucket."""
    ruta_local = Path(ruta_local)
    if not ruta_local.exists():
        return False
    try:
        return subir_bytes(clave, ruta_local.read_bytes())
    except Exception:
        return False


def bajar_bytes(clave: str) -> bytes | None:
    """Descarga un objeto. None si no existe o si no hay nube."""
    cfg = _config()
    if cfg is None:
        return None
    try:
        url = f"{cfg['url']}/storage/v1/object/{cfg['bucket']}/{clave}"
        r = requests.get(url, headers=_headers(cfg), timeout=TIMEOUT_NUBE)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def bajar_archivo(clave: str, ruta_local: str | Path) -> bool:
    """Descarga un objeto del bucket a una ruta local."""
    datos = bajar_bytes(clave)
    if datos is None:
        return False
    try:
        ruta_local = Path(ruta_local)
        ruta_local.parent.mkdir(parents=True, exist_ok=True)
        ruta_local.write_bytes(datos)
        return True
    except Exception:
        return False


def listar(prefijo: str = "") -> list[str]:
    """Lista las claves bajo un prefijo, p. ej. 'documentos'."""
    cfg = _config()
    if cfg is None:
        return []
    try:
        url = f"{cfg['url']}/storage/v1/object/list/{cfg['bucket']}"
        carpeta = prefijo.rstrip("/")
        r = requests.post(
            url,
            json={"prefix": carpeta, "limit": 1000,
                  "sortBy": {"column": "name", "order": "asc"}},
            headers=_headers(cfg, {"Content-Type": "application/json"}),
            timeout=TIMEOUT_NUBE,
        )
        if r.status_code != 200:
            return []
        claves = []
        for it in r.json():
            nombre = it.get("name")
            if not nombre or nombre == ".emptyFolderPlaceholder":
                continue
            claves.append(f"{carpeta}/{nombre}" if carpeta else nombre)
        return claves
    except Exception:
        return []


def eliminar(clave: str) -> bool:
    """Borra un objeto del bucket."""
    cfg = _config()
    if cfg is None:
        return False
    try:
        url = f"{cfg['url']}/storage/v1/object/{cfg['bucket']}/{clave}"
        r = requests.delete(url, headers=_headers(cfg), timeout=TIMEOUT_NUBE)
        return r.status_code in (200, 204)
    except Exception:
        return False


def probar_conexion() -> tuple[bool, str]:
    """
    Diagnóstico para la pantalla: dice QUÉ falla, no solo que falla.
    Devuelve (ok, mensaje).
    """
    cfg = _config()
    if requests is None:
        return False, "Falta la librería 'requests' en el entorno."
    if cfg is None:
        return False, ("Sin credenciales: agregá [supabase] url/key/bucket "
                       "en los Secrets de Streamlit.")
    try:
        url = f"{cfg['url']}/storage/v1/object/list/{cfg['bucket']}"
        r = requests.post(
            url, json={"prefix": "", "limit": 1},
            headers=_headers(cfg, {"Content-Type": "application/json"}),
            timeout=TIMEOUT_NUBE,
        )
        if r.status_code == 200:
            return True, f"Conectado al bucket '{cfg['bucket']}'."
        if r.status_code in (400, 404):
            return False, (f"El bucket '{cfg['bucket']}' no existe o el nombre "
                           f"no coincide (respuesta {r.status_code}).")
        if r.status_code in (401, 403):
            return False, ("La llave no tiene permiso sobre el bucket "
                           f"(respuesta {r.status_code}). ¿Es la service_role?")
        return False, f"Respuesta inesperada de Supabase: {r.status_code}."
    except Exception as e:
        return False, f"No se pudo hablar con Supabase: {e}"


# ════════════════════════════════════════════════════════════════════
# CLAVES DEL BUCKET (fuente única: nadie arma rutas a mano)
# ════════════════════════════════════════════════════════════════════

def clave_documento(nombre: str) -> str:
    return f"{PREFIJO_DOCS}/{nombre}"


def clave_estado(nombre: str) -> str:
    return f"{PREFIJO_ESTADO}/{nombre}"


# ════════════════════════════════════════════════════════════════════
# ESTADO JSON CON GUARDA (regla 3 del encabezado)
# ════════════════════════════════════════════════════════════════════

def leer_json_remoto(nombre: str) -> dict | None:
    """Lee un JSON de estado del bucket. None si no hay nube o no existe."""
    datos = bajar_bytes(clave_estado(nombre))
    if datos is None:
        return None
    try:
        return json.loads(datos.decode("utf-8"))
    except Exception:
        return None


def subir_json_con_guarda(nombre: str, contenido: dict,
                          permitir_reduccion: bool = False) -> tuple[bool, str]:
    """
    Sube un JSON de estado al bucket VERIFICANDO que no estemos pisando
    un registro con más entradas.

    permitir_reduccion=True se usa SOLO cuando el usuario borró un
    documento a propósito: ahí la reducción es el resultado esperado.

    Devuelve (subió, mensaje) para poder avisar en pantalla.
    """
    if not nube_activa():
        return False, "Sin nube configurada: el cambio quedó solo en este servidor."
    remoto = leer_json_remoto(nombre)
    if remoto is not None and not permitir_reduccion:
        if len(remoto) > len(contenido):
            return False, (
                f"BLOQUEADO: en la nube hay {len(remoto)} documentos y se iba a "
                f"subir un registro con {len(contenido)}. No se sobrescribió "
                "nada. Recargá la página para traer lo que está en la nube."
            )
    ok = subir_bytes(clave_estado(nombre),
                     json.dumps(contenido, ensure_ascii=False, indent=2).encode("utf-8"))
    return (ok, "Guardado en la nube." if ok else "Falló la subida a la nube.")


# ════════════════════════════════════════════════════════════════════
# HIDRATACIÓN (bajar lo que falte al arrancar)
# ════════════════════════════════════════════════════════════════════

def hidratar(forzar: bool = False) -> dict:
    """
    Baja del bucket a disco lo que falte: estado (registro, índice,
    instrucciones) y los documentos originales.

    Se hace UNA vez por sesión salvo forzar=True. Devuelve un resumen
    {'estado': n, 'documentos': n, 'nube': bool} para poder mostrarlo.
    """
    resumen = {"estado": 0, "documentos": 0, "nube": nube_activa()}
    if not resumen["nube"]:
        return resumen
    try:
        import streamlit as st
        if not forzar and st.session_state.get("_nube_hidratada"):
            return resumen
    except Exception:
        st = None

    try:
        for clave in listar(PREFIJO_ESTADO):
            destino = ESTADO_DIR / Path(clave).name
            if forzar or not destino.exists():
                if bajar_archivo(clave, destino):
                    resumen["estado"] += 1
        for clave in listar(PREFIJO_DOCS):
            destino = DOCS_DIR / Path(clave).name
            if forzar or not destino.exists():
                if bajar_archivo(clave, destino):
                    resumen["documentos"] += 1
        if st is not None:
            st.session_state["_nube_hidratada"] = True
    except Exception:
        pass
    return resumen
