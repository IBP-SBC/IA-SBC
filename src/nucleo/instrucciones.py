"""
nucleo/instrucciones.py
=======================
main.md: las INSTRUCCIONES GENERALES de la conversación. Es el archivo
que define quién es el asistente, cómo responde, qué no puede hacer y
con qué criterio prioriza (círculo dorado, simplicidad, citar la fuente).

POR QUÉ un archivo y no texto quemado en el código: la forma de
conversar es una decisión de NEGOCIO, no de programación. Alberto —o
quien tenga el rol admin— debe poder cambiarla desde la app, sin tocar
el repositorio ni esperar un despliegue.

DÓNDE VIVE, en este orden de prioridad:
  1. data/estado/main.md  → la versión editada desde la app (y la que se
     sincroniza con el bucket de Supabase);
  2. main.md en la raíz del repo → la semilla que viaja en GitHub.
Si no existe ninguna, se usa el texto por defecto de este módulo, para
que la app NUNCA arranque sin instrucciones.
"""
from __future__ import annotations

from nucleo import nube
from nucleo.config import ESTADO_DIR, RUTA_MAIN, RUTA_MAIN_LOCAL
from nucleo.util import sello_ahora

ARCHIVO_MAIN = "main.md"          # clave dentro de estado/ en el bucket

MAIN_POR_DEFECTO = """# Instrucciones generales · IA-SBC

Sos el asistente de la Sociedad Bíblica Colombiana (SBC). Tu trabajo es
ayudar a líderes y colaboradores a tomar mejores decisiones del día a día
usando lo que la SBC YA tiene estudiado y escrito.

## Cómo respondés
1. **Empezá por el PORQUÉ.** Antes del dato, decí qué problema resuelve.
2. **Simple.** Frases cortas, sin jerga innecesaria. Menos es más.
3. **Con la fuente a la vista.** Cada afirmación que salga de un
   documento va citada así: (Documento, ubicación).
4. **Si no está en los documentos, decilo.** Es preferible "esto no está
   en lo que tengo cargado" a una respuesta inventada que suene bien.
5. **Español de Colombia**, tono cercano y profesional.

## Qué NO hacés
- No inventás cifras, fechas ni nombres.
- No mezclás lo que dice un documento con tu opinión sin avisar cuál es
  cuál.
- No das por cierto algo porque "suena razonable".

## Cuando la pregunta es una decisión
Respondé en este orden: qué dicen los documentos → qué implica para la
decisión → qué falta por confirmar y con quién.
"""


def leer_instrucciones() -> str:
    """Devuelve el texto de main.md vigente (nunca vacío)."""
    # 1. versión editada (disco; si falta, se intenta la nube)
    if not RUTA_MAIN_LOCAL.exists():
        nube.bajar_archivo(nube.clave_estado(ARCHIVO_MAIN), RUTA_MAIN_LOCAL)
    for ruta in (RUTA_MAIN_LOCAL, RUTA_MAIN):
        try:
            if ruta.exists():
                txt = ruta.read_text(encoding="utf-8").strip()
                if txt:
                    return txt
        except Exception:
            continue
    return MAIN_POR_DEFECTO


def guardar_instrucciones(texto: str, usuario: str) -> str:
    """
    Guarda main.md en disco y en el bucket. Devuelve un mensaje para
    mostrar en pantalla.

    No se permite guardar vacío: dejar al asistente sin instrucciones lo
    convierte en un chat genérico, que es justo lo que no queremos.
    """
    texto = (texto or "").strip()
    if len(texto) < 50:
        return ("No se guardó: las instrucciones quedaron demasiado cortas "
                "(mínimo 50 caracteres). El asistente sin instrucciones "
                "responde como un chat genérico.")
    sello = f"\n\n<!-- Última edición: {usuario} · {sello_ahora()} -->\n"
    contenido = texto + sello
    try:
        ESTADO_DIR.mkdir(parents=True, exist_ok=True)
        RUTA_MAIN_LOCAL.write_text(contenido, encoding="utf-8")
    except Exception as e:
        return f"No se pudo escribir en disco: {e}"
    ok = nube.subir_bytes(nube.clave_estado(ARCHIVO_MAIN),
                          contenido.encode("utf-8"))
    if not nube.nube_activa():
        return ("Guardado en este servidor. OJO: sin Supabase configurado, "
                "el cambio se pierde en el próximo reinicio.")
    return ("Guardado y sincronizado con la nube." if ok
            else "Guardado en disco, pero FALLÓ la subida a la nube.")


def restaurar_por_defecto(usuario: str) -> str:
    """Vuelve a la semilla del repositorio (o al texto de fábrica)."""
    try:
        base = RUTA_MAIN.read_text(encoding="utf-8") if RUTA_MAIN.exists() \
            else MAIN_POR_DEFECTO
    except Exception:
        base = MAIN_POR_DEFECTO
    return guardar_instrucciones(base, usuario)
