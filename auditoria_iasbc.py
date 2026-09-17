"""
auditoria_iasbc.py
==================
No comprueba "que no truene": comprueba que los datos LLEGUEN y
SIGNIFIQUEN lo correcto. Cada check nació de un riesgo real de esta app,
no de un caso inventado.

Se corre desde la carpeta del proyecto, ANTES de subir a GitHub:

    python3 validar_ast.py && python3 auditoria_iasbc.py

Sale con código 1 si algún check falla, para poder encadenarlo.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

# Se trabaja sobre un directorio temporal: la auditoría NO debe tocar los
# documentos reales ni dejar archivos en data/ (el repo viaja limpio).
_TMP = Path(tempfile.mkdtemp(prefix="auditoria_iasbc_"))

import nucleo.config as config  # noqa: E402

config.DATA_DIR = _TMP
config.DOCS_DIR = _TMP / "documentos"
config.ESTADO_DIR = _TMP / "estado"
config.RUTA_REGISTRO = config.ESTADO_DIR / "registro.json"
config.RUTA_CHUNKS = config.ESTADO_DIR / "fragmentos.parquet"
config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
config.ESTADO_DIR.mkdir(parents=True, exist_ok=True)

import nucleo.indice as indice  # noqa: E402
import nucleo.nube as nube  # noqa: E402
from nucleo import extraccion, modelo, util  # noqa: E402

# El módulo indice importó las rutas por valor: hay que apuntarlas al tmp.
indice.DOCS_DIR = config.DOCS_DIR
indice.ESTADO_DIR = config.ESTADO_DIR
indice.RUTA_REGISTRO = config.RUTA_REGISTRO
indice.RUTA_CHUNKS = config.RUTA_CHUNKS

# Sin nube durante la auditoría: los checks miden la LÓGICA, no la red.
nube.nube_activa = lambda: False
nube.subir_bytes = lambda *a, **k: False
nube.subir_archivo = lambda *a, **k: False
nube.bajar_bytes = lambda *a, **k: None
nube.bajar_archivo = lambda *a, **k: False
nube.leer_json_remoto = lambda *a, **k: None
nube.eliminar = lambda *a, **k: False

_OK = 0
_FALLOS: list[str] = []


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    global _OK
    if condicion:
        _OK += 1
        print(f"  ✓ {nombre}")
    else:
        _FALLOS.append(f"{nombre} — {detalle}")
        print(f"  ✗ {nombre}  → {detalle}")


TEXTO_PRUEBA = (
    "El segmento S5 Influenciado-Inseguro representa el 16% del cluster 4 "
    "y es el segmento critico sub-atendido por la SBC.\n\n"
    "La meta de biblias 2026 es de 1.365.564 unidades, con un presupuesto "
    "total de 41.386.063.026 pesos colombianos.\n\n"
    "La planta de encuaderna cion tiene una capacidad minima rentable de "
    "54.000 unidades mensuales y un lote minimo de 800 unidades.\n\n"
) * 3


print("\n═══ 1. CONFIGURACIÓN Y ENTORNO ═══")
check("El bucket NO es el de las otras apps",
      config.BUCKET_DEFECTO not in ("sbc-datos", "sbc-demanda"),
      f"BUCKET_DEFECTO={config.BUCKET_DEFECTO} pisaría los datos de otra app")
check("main.md existe en el repositorio", config.RUTA_MAIN.exists(),
      "sin la semilla, la app arranca sin instrucciones")
check("main.md tiene contenido real",
      config.RUTA_MAIN.exists() and len(config.RUTA_MAIN.read_text()) > 500,
      "las instrucciones no pueden ser un placeholder")
check("Todas las extensiones declaradas tienen extractor",
      set(config.EXTENSIONES_SOPORTADAS) <= set(extraccion._MAPA),
      f"sin extractor: {set(config.EXTENSIONES_SOPORTADAS) - set(extraccion._MAPA)}")

print("\n═══ 2. HORA Y TEXTO ═══")
from datetime import datetime, timezone  # noqa: E402

_desfase = (util.ahora_bogota().utcoffset().total_seconds() / 3600)
check("Los sellos van en hora de Bogotá (UTC-5)", _desfase == -5,
      f"desfase detectado: {_desfase}h — se mostraría la hora del contenedor")
check("La normalización quita tildes y mayúsculas",
      util.normalizar("Biblía CÓN Referencias") == "biblia con referencias")
check("Los códigos numéricos sobreviven a la tokenización",
      "0001" in util.tokenizar("la linea 0001 es encuadernacion"),
      "si se pierden los códigos, no se puede preguntar por un ISBN")
check("Singular y plural se buscan igual",
      util.tokenizar("jóvenes recursos")[0] == util.tokenizar("joven")[0],
      "'jóvenes' no encontraría un párrafo que dice 'el joven'")
check("El recorte de plurales NO toca los códigos",
      util.raiz_ligera("9786287835641") == "9786287835641")

print("\n═══ 2-bis. EXTENSIÓN vs CONTENIDO REAL ═══")
# Caso real: varios 'PDF' de la SBC son por dentro archivos de Office.
_zip_falso = b"PK\x03\x04" + b"\x00" * 40
check("Un .pdf que por dentro es otra cosa se rechaza explicando",
      "por dentro" in extraccion.revisar_coherencia("Informe.pdf", _zip_falso),
      "sin este aviso el usuario ve 'Stream has ended unexpectedly'")
check("Un .docx que es texto plano se rechaza explicando",
      "texto plano" in extraccion.revisar_coherencia("Estrategia.docx", b"**Articulo 1"),
      "")
check("Un archivo coherente NO se bloquea",
      extraccion.revisar_coherencia("nota.txt", b"hola") == ""
      and extraccion.revisar_coherencia("doc.pdf", b"%PDF-1.7 ...") == "")

print("\n═══ 3. TROCEO ═══")
frags = indice.trocear(TEXTO_PRUEBA)
check("El troceo produce fragmentos", len(frags) > 0)
check("Ningún fragmento excede el tamaño configurado",
      all(len(f) <= config.TAM_FRAGMENTO + config.SOLAPE_FRAGMENTO + 50 for f in frags),
      f"máximo real: {max((len(f) for f in frags), default=0)}")
check("No se pierde contenido en el troceo",
      "41.386.063.026" in " ".join(frags),
      "una cifra del texto original desapareció al trocear")

print("\n═══ 4. INDEXADO Y UPSERT POR NOMBRE ═══")
r1 = indice.indexar_documento("Plan prueba.txt", TEXTO_PRUEBA.encode("utf-8"), "auditoria")
check("Se indexa un documento nuevo", r1.get("ok"), r1.get("mensaje", ""))
n1 = len(indice.leer_chunks())

r2 = indice.indexar_documento("Plan prueba.txt",
                              (TEXTO_PRUEBA + "Texto agregado en la version dos.").encode("utf-8"),
                              "auditoria")
df2 = indice.leer_chunks()
check("Subir el MISMO nombre actualiza, no duplica",
      r2.get("actualizado") is True and len(indice.leer_registro()) == 1,
      f"registro quedó con {len(indice.leer_registro())} documentos")
check("Los fragmentos viejos del documento se reemplazan",
      int((df2['documento'] == 'Plan prueba.txt').sum()) == r2['fragmentos'],
      f"quedaron {int((df2['documento'] == 'Plan prueba.txt').sum())} de {r2['fragmentos']}")

r3 = indice.indexar_documento("Plan prueba v2.txt", TEXTO_PRUEBA.encode("utf-8"), "auditoria")
check("Un nombre PARECIDO es otro documento (no se adivinan identidades)",
      len(indice.leer_registro()) == 2,
      "se fusionaron dos documentos distintos")

check("Un archivo sin texto se RECHAZA con mensaje",
      indice.indexar_documento("vacio.txt", b"   ", "auditoria").get("ok") is False,
      "un documento vacío aparecería en la lista como si la IA lo conociera")
check("Una extensión no soportada se rechaza explicando",
      not extraccion.extraer("archivo.zip", b"x").ok)

print("\n═══ 5. BÚSQUEDA ═══")
res = indice.buscar("¿cuál es el lote mínimo de la planta?", k=5)
check("La búsqueda encuentra el fragmento correcto",
      (not res.empty) and "800" in res.iloc[0]["texto"],
      "el fragmento con la respuesta no quedó primero")
check("Los puntajes vienen ordenados de mayor a menor",
      res["puntaje"].is_monotonic_decreasing)
check("Buscar en un documento inexistente devuelve vacío, no error",
      indice.buscar("lote", documentos=["no existe.pdf"]).empty)
check("Una pregunta sin términos buscables devuelve vacío",
      indice.buscar("de la y el").empty,
      "con solo palabras vacías no se puede rankear: no hay que inventar un orden")

print("\n═══ 6. CONTEXTO QUE VIAJA AL MODELO ═══")
system = modelo.construir_system(res)
check("El system incluye las instrucciones del negocio",
      "Sociedad Bíblica Colombiana" in system or "SBC" in system)
check("El system incluye las reglas fijas", "NO NEGOCIABLES" in system)
check("Los fragmentos van etiquetados para poder citarlos", "[F1]" in system)
import pandas as _pd  # noqa: E402
check("Sin fragmentos, se le dice al modelo que NO hay respaldo",
      "NO SE ENCONTRÓ" in modelo.construir_system(_pd.DataFrame()),
      "sin este aviso, el modelo responde de memoria y parece documentado")

_fuente_modelo = (RAIZ / "src/nucleo/modelo.py").read_text(encoding="utf-8")
check("No se envía 'temperature' a la API",
      '"temperature"' not in _fuente_modelo,
      "en los modelos 5 cualquier temperatura distinta del defecto da error 400")
check("La llave de la API no está escrita en el código",
      "sk-ant-" not in _fuente_modelo.replace('sk-ant-..."', ""),
      "una llave en el repositorio es una llave quemada")

print("\n═══ 6-bis. PROVEEDOR DEL MODELO ═══")
check("Sin proveedor configurado, la app NO truena",
      modelo.configuracion() is None and modelo.estado()[0] is False,
      "sin llave la app debe caer en modo búsqueda, no en un error")
_salida = "".join(modelo.responder_streaming("lote minimo", [], res))
check("Sin proveedor, responde con los PASAJES y no inventa",
      "Modo búsqueda" in _salida and "800" in _salida,
      "el modo búsqueda debe mostrar el contenido real encontrado")
check("El modo búsqueda cita el documento de cada pasaje",
      "Plan prueba.txt" in _salida,
      "un pasaje sin fuente no se puede verificar")
_lineas = _fuente_modelo.splitlines()
check("Un solo lugar lee el protocolo SSE",
      sum(1 for l in _lineas if "def _eventos_sse" in l) == 1,
      "duplicar el parser es duplicar los bugs")
_err404 = modelo._mensaje_de_error(
    404, '{"error": {"message": "models/x is not found for API version v1beta",'
         ' "status": "NOT_FOUND"}}')
check("Un error del proveedor muestra lo que el proveedor dijo",
      "is not found for API version" in _err404,
      "esconder el detalle del error fue un bug real de la v1.1.0: la app "
      "culpaba al nombre del modelo cuando el modelo estaba en la lista")
check("El error también dice qué hacer, no solo el código",
      "Probar modelo" in _err404 or "conversación" in _err404)
_todos = ["gemini-3.5-flash", "gemini-embedding-2", "veo-3.1-generate-preview",
          "gemini-2.5-flash-preview-tts", "nano-banana-pro-preview",
          "gemini-flash-latest", "gemini-2.5-flash-image"]
_chat = modelo.modelos_para_conversar(_todos)
check("Se filtran los modelos que no conversan (imagen, audio, video…)",
      set(_chat) == {"gemini-3.5-flash", "gemini-flash-latest"},
      f"quedaron: {_chat}")
check("Google se atiende por la base compatible con OpenAI",
      "generativelanguage.googleapis.com" in
      (RAIZ / "src/nucleo/config.py").read_text(encoding="utf-8"),
      "sin esa base habría que escribir un segundo cliente completo")

print("\n═══ 6-ter. CODIFICACIÓN DEL STREAM (tildes y eñes) ═══")
# Bug real de la v1.1.1: requests asume ISO-8859-1 cuando el servidor
# manda 'text/*' sin charset, y las tildes llegaban rotas
# ("Activo-Público" se veía "Activo-PÃºblico"). Se prueba con los TRES
# casos posibles, con acentos reales.
import io as _io  # noqa: E402
import requests as _req  # noqa: E402
from urllib3 import HTTPResponse as _HR  # noqa: E402

_LINEA = ('data: {"choices":[{"delta":{"content":"Activo-Público qué año"}}]}'
          '\n').encode("utf-8")


def _respuesta_simulada(encoding):
    r = _req.Response()
    r.status_code = 200
    r.encoding = encoding
    r.raw = _HR(body=_io.BytesIO(_LINEA),
                headers={"Content-Type": "text/event-stream"},
                status=200, preload_content=False)
    return r


for _enc in ("ISO-8859-1", "utf-8", None):
    _eventos = list(modelo._eventos_sse(_respuesta_simulada(_enc)))
    _texto = "".join(e["choices"][0]["delta"]["content"] for e in _eventos)
    check(f"Las tildes llegan bien con encoding={_enc}",
          _texto == "Activo-Público qué año",
          f"se recibió: {_texto!r}")

print("\n═══ 6-quater. CUANDO EL MODELO NO ESCRIBE NADA ═══")
# Caso real: una pregunta quedó sin respuesta y la MISMA pregunta
# funcionó tras reiniciar la app. Dos causas posibles, las dos cubiertas.
_hist = [{"role": "user", "content": "hola"},
         {"role": "assistant", "content": ""},      # respuesta vacía guardada
         {"role": "user", "content": "  "},          # turno en blanco
         {"role": "sistema", "content": "x"}]        # rol inválido
_validos = modelo.turnos_validos(_hist)
check("Los turnos vacíos no se le mandan al proveedor",
      _validos == [{"role": "user", "content": "hola"}],
      f"quedaron: {_validos}")
_vacio = modelo.mensaje_respuesta_vacia("length")
check("Una respuesta vacía se EXPLICA, no deja el chat mudo",
      "presupuesto de tokens" in _vacio and "Qué hacer" in _vacio)
check("Un motivo desconocido también se explica",
      "raro_nuevo" in modelo.mensaje_respuesta_vacia("raro_nuevo"),
      "si el motivo es nuevo hay que mostrarlo, no esconderlo")

print("\n═══ 7. BORRADO Y GUARDA ANTI-PISADO ═══")
msg = indice.eliminar_documento("Plan prueba v2.txt")
check("Eliminar saca el documento del registro",
      "Plan prueba v2.txt" not in indice.leer_registro(), msg)
check("Eliminar saca sus fragmentos del índice",
      int((indice.leer_chunks()["documento"] == "Plan prueba v2.txt").sum()) == 0)

# La guarda se prueba con la función real, simulando que la nube tiene más.
nube.nube_activa = lambda: True
nube.leer_json_remoto = lambda nombre: {"a": 1, "b": 2, "c": 3}
ok_guarda, msg_guarda = nube.subir_json_con_guarda("registro.json", {"a": 1})
check("La guarda BLOQUEA pisar un registro remoto con más documentos",
      ok_guarda is False and "BLOQUEADO" in msg_guarda,
      "este es exactamente el patrón que borró histórico tres veces en sbc_ventas")
_ok_borrado, msg_borrado = nube.subir_json_con_guarda(
    "registro.json", {"a": 1}, permitir_reduccion=True)
check("Un borrado explícito NO queda bloqueado por la guarda",
      "BLOQUEADO" not in msg_borrado,
      "si la guarda también bloquea los borrados, no se podría quitar un "
      "documento desactualizado")
nube.nube_activa = lambda: False
nube.leer_json_remoto = lambda *a, **k: None

print("\n═══ 8. ARQUITECTURA ═══")
_fuentes_nucleo = list((RAIZ / "src/nucleo").rglob("*.py"))
_dibujan = []
for p in _fuentes_nucleo:
    txt = p.read_text(encoding="utf-8")
    if any(f"st.{w}(" in txt for w in ("write", "markdown", "dataframe",
                                       "button", "title", "header")):
        _dibujan.append(p.name)
check("nucleo/ no dibuja (app/ no calcula, nucleo/ no dibuja)",
      not _dibujan, f"dibujan: {_dibujan}")

_paginas = list((RAIZ / "src/app/paginas").glob("*.py"))
check("Las páginas registradas en Home.py existen",
      all((RAIZ / "src/app/paginas" / n).exists()
          for n in ("conversacion.py", "documentos.py", "instrucciones.py")))
_home = (RAIZ / "src/app/Home.py").read_text(encoding="utf-8")
check("exigir_login() se llama SOLO desde Home.py",
      all("exigir_login()" not in p.read_text(encoding="utf-8") for p in _paginas),
      "llamarlo dos veces duplica la key del botón 'Salir' y truena")
_css = (RAIZ / "src/app/ui.py").read_text(encoding="utf-8")
check("El estilo no fija fondos ni textos que rompan el modo oscuro",
      not any(x in _css.lower() for x in ("background: #fff", "background:#fff",
                                          "color: #000", "color:#000",
                                          "color: white", "color: #fff")),
      "un color fijo deja texto ilegible en uno de los dos temas")
# Se miran solo las líneas ACTIVAS: el archivo menciona [theme] en un
# comentario, justamente para advertir que no hay que usarlo.
_toml = [l.strip() for l in
         (RAIZ / ".streamlit/config.toml").read_text(encoding="utf-8").splitlines()
         if l.strip() and not l.strip().startswith("#")]
check("config.toml NO define [theme]",
      "[theme]" not in _toml,
      "definir [theme] fuerza el modo claro para todos los usuarios")
check("El repositorio viaja sin datos",
      not any(p.name != ".gitkeep" for p in (RAIZ / "data").rglob("*") if p.is_file()),
      "data/ debe ir vacío: los documentos viven en Supabase")

print("\n" + "═" * 60)
if _FALLOS:
    print(f"RESULTADO: {_OK} checks OK · {len(_FALLOS)} FALLAS\n")
    for f in _FALLOS:
        print(f"  ✗ {f}")
    sys.exit(1)
print(f"RESULTADO: {_OK} checks OK · sin fallas")
