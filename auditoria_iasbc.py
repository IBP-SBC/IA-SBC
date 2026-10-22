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

print("\n═══ 4-bis. LA BARRERA ENTRE LO PÚBLICO Y LO INTERNO ═══")
# Es el check más importante de la app: si esto falla, el presupuesto de
# la SBC queda consultable por cualquiera que abra el enlace.
indice.indexar_documento("Guia biblica.txt",
                         ("La oracion y la lectura biblica son practicas "
                          "centrales de la vida cristiana.\n\n" * 4).encode("utf-8"),
                         "auditoria", ambito=indice.AMBITO_PUBLICO)
indice.indexar_documento("Presupuesto secreto.txt",
                         ("El presupuesto 2026 asciende a 41.386.063.026 pesos "
                          "distribuidos entre los canales.\n\n" * 4).encode("utf-8"),
                         "auditoria", ambito=indice.AMBITO_INTERNO)

_pub = indice.buscar("presupuesto 2026 pesos", k=10,
                     ambito=indice.AMBITO_PUBLICO)
check("Una búsqueda pública NO alcanza un documento interno",
      _pub.empty or "Presupuesto secreto.txt" not in set(_pub["documento"]),
      f"se filtró: {sorted(set(_pub['documento'])) if not _pub.empty else ''}")

_forzado = indice.buscar("presupuesto", k=10,
                         documentos=["Presupuesto secreto.txt"],
                         ambito=indice.AMBITO_PUBLICO)
check("Pedir un documento interno desde el lado público devuelve vacío",
      _forzado.empty,
      "el filtro por documento no puede saltarse la barrera de ámbito")

_interno = indice.buscar("presupuesto 2026 pesos", k=10, ambito=None)
check("El administrador SÍ alcanza lo interno",
      not _interno.empty and "Presupuesto secreto.txt" in set(_interno["documento"]))

check("Un documento sin ámbito declarado cuenta como interno",
      "Plan prueba.txt" in indice.documentos_del_ambito(indice.AMBITO_INTERNO),
      "los documentos viejos no traen ámbito: equivocarse hacia el lado "
      "cerrado deja un documento sin usar, hacia el abierto lo publica")

indice.reconstruir_indice("auditoria")
check("Reconstruir el índice CONSERVA el ámbito de cada documento",
      indice.leer_registro()["Guia biblica.txt"]["ambito"] == indice.AMBITO_PUBLICO
      and indice.leer_registro()["Presupuesto secreto.txt"]["ambito"] == indice.AMBITO_INTERNO,
      "si se perdiera, un documento interno podría quedar público")

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

print("\n═══ 5-bis. COTIZADOR: NI UN PRECIO INVENTADO ═══")
import pandas as _pd  # noqa: E402
from nucleo import cotizador  # noqa: E402

cotizador.RUTA_PRECIOS = config.ESTADO_DIR / "precios.parquet"
cotizador.RUTA_ADICIONALES = config.ESTADO_DIR / "precios_adicionales.parquet"

_sin = cotizador.cotizar("Biblia", 1000, {})
check("Sin lista de precios NO se inventa un valor",
      _sin["ok"] is False and _sin["motivo"] == "sin_tabla"
      and "$" not in _sin["mensaje"],
      "un 'precio de referencia' sacado de la nada termina en un reclamo")

_tabla = _pd.DataFrame([
    {"familia": "Biblia", "referencia": "Agenda 13x21", "version": "RVR",
     "tamano": "13x21 agenda", "cubierta": "Imitación piel",
     "desde_cantidad": 800, "precio_unitario": 30000, "minimo": 800,
     "dias_entrega": 90, "incluye": "Logo en cubierta"},
    {"familia": "Biblia", "referencia": "Agenda 13x21", "version": "RVR",
     "tamano": "13x21 agenda", "cubierta": "Imitación piel",
     "desde_cantidad": 2400, "precio_unitario": 27000, "minimo": 800,
     "dias_entrega": 90, "incluye": "Logo en cubierta"},
])
_tabla.to_parquet(cotizador.RUTA_PRECIOS, index=False)
_pd.DataFrame([{"concepto": "Grabado del nombre", "tipo": "unitario",
                "valor": 1500, "aplica_a": "todas"},
               {"concepto": "Diseño de la cubierta", "tipo": "fijo",
                "valor": 200000, "aplica_a": "todas"}]
              ).to_parquet(cotizador.RUTA_ADICIONALES, index=False)

_bajo = cotizador.cotizar("Biblia", 50, {"version": "RVR"})
check("Por debajo del mínimo se avisa ANTES de cotizar",
      _bajo["ok"] is False and _bajo["motivo"] == "bajo_minimo"
      and _bajo["minimo"] == 800,
      "enterarse al final del mínimo de planta es peor que saberlo al inicio")

_mil = cotizador.cotizar("Biblia", 1000, {"version": "RVR"})
check("Se aplica la escala correcta por cantidad",
      _mil["ok"] and _mil["unitario"] == 30000 and _mil["total"] == 30_000_000,
      f"dio: {_mil.get('unitario')} · {_mil.get('total')}")

_tresmil = cotizador.cotizar("Biblia", 3000, {"version": "RVR"})
check("Una cantidad mayor toma el precio de la escala superior",
      _tresmil["ok"] and _tresmil["unitario"] == 27000,
      f"dio: {_tresmil.get('unitario')}")

_con_adic = cotizador.cotizar("Biblia", 1000, {"version": "RVR"},
                              ["Grabado del nombre", "Diseño de la cubierta"])
check("Los adicionales unitarios se multiplican y los fijos no",
      _con_adic["total"] == 30_000_000 + 1500 * 1000 + 200_000,
      f"total: {_con_adic.get('total')}")
check("El unitario mostrado incluye los adicionales",
      abs(_con_adic["unitario_con_adicionales"]
          - _con_adic["total"] / 1000) < 0.01,
      "el cliente compara por unidad: ese número tiene que cuadrar")
check("La cotización dice el tiempo de entrega real",
      _mil["dias_entrega"] == 90)

_ok_carga, _msg_carga = cotizador.cargar_tabla(
    b"familia,referencia,version,tamano,cubierta,desde_cantidad,"
    b"precio_unitario,minimo,dias_entrega,incluye\n"
    b"Biblia,X,RVR,13x21,Piel,800,0,800,90,nada\n", "precios.csv", "auditoria")
check("Una tabla con precio en cero se RECHAZA entera",
      _ok_carga is False and "cero" in _msg_carga.lower(),
      "guardar un cero silencioso haría cotizar en 0 sin que nadie lo note")
check("Tras rechazar, la tabla anterior sigue intacta",
      len(cotizador.leer_precios()) == 2,
      "una carga inválida no puede dejar a la app sin precios")


print("\n═══ 5-ter. AGREGADOS POR FAMILIA Y LISTA DE PRUEBA ═══")
# Bug real de la v2.2: el agregado se buscaba solo por concepto; si la
# primera fila era de otra familia, desaparecía sin aviso.
_pd.DataFrame([{"familia": "Nuevo Testamento", "referencia": "NT", "version": "RVR",
                "tamano": "B", "cubierta": "T", "desde_cantidad": 1000,
                "precio_unitario": 6500, "minimo": 1000, "dias_entrega": 45,
                "incluye": ""}]).to_parquet(cotizador.RUTA_PRECIOS, index=False)
_pd.DataFrame([{"concepto": "Inserto", "tipo": "unitario", "valor": 1500, "aplica_a": "Biblia"},
               {"concepto": "Inserto", "tipo": "unitario", "valor": 1200, "aplica_a": "Nuevo Testamento"},
               {"concepto": "Sello", "tipo": "fijo", "valor": 9000, "aplica_a": "todas"},
               {"concepto": "Sello", "tipo": "fijo", "valor": 7000, "aplica_a": "Nuevo Testamento"}]
              ).to_parquet(cotizador.RUTA_ADICIONALES, index=False)
_nt = cotizador.cotizar("Nuevo Testamento", 1000, {"version": "RVR"}, ["Inserto", "Sello"])
check("Un agregado con precio por familia se cobra con el de ESA familia",
      _nt["ok"] and _nt["total"] == 6_500_000 + 1200 * 1000 + 7000,
      f"total {_nt.get('total')}: antes de la v2.3 el inserto desaparecía sin aviso")
check("El precio propio de la familia gana sobre el general ('todas')",
      any(a["concepto"] == "Sello" and a["monto"] == 7000 for a in _nt["adicionales"]))
check("Solo se ofrecen los agregados que aplican a la familia",
      cotizador.adicionales_para("Tratado") == ["Sello"]
      and cotizador.adicionales_para("Nuevo Testamento") == ["Inserto", "Sello"])

def _xlsx(precios_df, adic_df=None):
    import io as _io2
    buf = _io2.BytesIO()
    with _pd.ExcelWriter(buf, engine="openpyxl") as w:
        precios_df.to_excel(w, sheet_name="precios", index=False)
        if adic_df is not None:
            adic_df.to_excel(w, sheet_name="adicionales", index=False)
    return buf.getvalue()

_base = _pd.read_parquet(cotizador.RUTA_PRECIOS)
_ok_t, _m_t = cotizador.cargar_tabla(_xlsx(_base, _pd.DataFrame(
    [{"concepto": "X", "tipo": "por caja", "valor": 10, "aplica_a": "todas"}])), "l.xlsx", "aud")
check("Un agregado con tipo desconocido se RECHAZA (antes se cobraba como fijo)",
      not _ok_t and "unitario" in _m_t)
_ok_v, _m_v = cotizador.cargar_tabla(_xlsx(_base, _pd.DataFrame(
    [{"concepto": "X", "tipo": "fijo", "valor": "$1.500", "aplica_a": "todas"}])), "l.xlsx", "aud")
check("Un valor escrito como texto se RECHAZA (antes se volvía $0 sin aviso)",
      not _ok_v and "número" in _m_v)
_ok_d, _m_d = cotizador.cargar_tabla(_xlsx(_base, _pd.DataFrame(
    [{"concepto": "X", "tipo": "fijo", "valor": 1, "aplica_a": "Biblia"},
     {"concepto": "X", "tipo": "fijo", "valor": 2, "aplica_a": "Biblia"}])), "l.xlsx", "aud")
check("Un concepto repetido para la misma familia se RECHAZA", not _ok_d and "repetidos" in _m_d)
check("Tras un rechazo, los agregados anteriores siguen intactos",
      len(cotizador.leer_adicionales()) == 4)
_ok_s, _ = cotizador.cargar_tabla(_xlsx(_base), "l.xlsx", "aud")
check("Una lista nueva SIN hoja de agregados borra los anteriores",
      _ok_s and cotizador.leer_adicionales().empty,
      "los agregados de una lista de prueba no pueden sobrevivir a la oficial")

_okp, _mp = cotizador.cargar_lista_de_prueba("aud")
check("La lista de prueba carga por el MISMO camino que una real", _okp, _mp)
check("La lista de prueba queda marcada como simulada", cotizador.es_simulada())
_c = cotizador.cotizar
_b800 = _c("Biblia", 800, {"version": "RVR"})
check("Prueba · 800 Biblias = 800 × $42.000 = $33.600.000",
      _b800["ok"] and _b800["total"] == 33_600_000, f"dio {_b800.get('total')}")
check("Prueba · 1.600 Biblias toman la escala de $39.900 = $63.840.000",
      _c("Biblia", 1600, {"version": "TLA"})["total"] == 63_840_000)
check("Prueba · 3.200 Biblias toman la escala de $37.800 = $120.960.000",
      _c("Biblia", 3200, {"version": "RVR"})["total"] == 120_960_000)
_comp = _c("Biblia", 800, {"version": "RVR"},
           ["Hoja de inserto personalizada", "Plancha de estampado de la cubierta"])
check("Prueba · 800 Biblias + inserto ($1.500 c/u) + plancha ($350.000 una vez) = $35.150.000",
      _comp["total"] == 33_600_000 + 1_200_000 + 350_000, f"dio {_comp.get('total')}")
check("Prueba · 1.000 NT + inserto de NT ($1.200 c/u) = $7.700.000",
      _c("Nuevo Testamento", 1000, {"version": "RVR"},
         ["Hoja de inserto personalizada"])["total"] == 7_700_000)
check("Prueba · 12.000 tratados toman la escala de $150 = $1.800.000",
      _c("Tratado", 12000, {})["total"] == 1_800_000)
check("Prueba · 1.500 Evangelios quedan bajo el mínimo de 2.000",
      _c("Evangelio", 1500, {"version": "RVR"})["motivo"] == "bajo_minimo")
check("Prueba · 'Producto propio' se cotiza a pedido, sin precio inventado",
      _c("Producto propio", 500, {})["motivo"] == "a_pedido")
check("La solicitud enviada con la lista de prueba lo dice en la primera línea",
      cotizador.texto_solicitud(_b800, {"familia": "Biblia"}, {}, simulada=True)
      .startswith("*** PRUEBA"))
cotizador.borrar_lista()
check("Quitar la lista de prueba deja el cotizador sin precios y sin marca",
      not cotizador.hay_precios() and not cotizador.es_simulada())

print("\n═══ 6. CONTEXTO QUE VIAJA AL MODELO ═══")
system = modelo.construir_system(res)
check("El system incluye las instrucciones del negocio",
      "Sociedad Bíblica Colombiana" in system or "SBC" in system)
check("El system incluye las reglas fijas", "NO NEGOCIABLES" in system)
check("Los fragmentos van etiquetados para poder citarlos", "[F1]" in system)
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

print("\n═══ 7-bis. DEMO MILLCA ═══")
from nucleo import millca  # noqa: E402

_rc = millca.resumen_corpus()
check("El texto de la demo viaja en el repo y es Juan completo",
      _rc["versiculos"] == 879 and _rc["capitulos"] == 21,
      f"se esperaban 879 versículos en 21 capítulos; hay {_rc}")
_j316 = millca.capitulo(3)
_j316 = _j316[_j316["versiculo"] == 16]["texto"].iloc[0] if not _j316.empty else ""
check("Juan 3:16 es el de la RV1909 (ortografía antigua, no RVR60)",
      "á su Hijo unigénito" in _j316,
      "si dice 'a su Hijo' sin tilde es otra versión y hay que revisar derechos")
check("El versículo del día no es aleatorio (misma pantalla para todos)",
      millca.versiculo_del_dia() == millca.versiculo_del_dia())
_yt = millca.clasificar_video("https://youtu.be/dQw4w9WgXcQ?si=abc")
check("Reconoce enlaces cortos de YouTube",
      _yt["plataforma"] == "youtube" and _yt["embed"].endswith("/embed/dQw4w9WgXcQ"))
_sh = millca.clasificar_video("https://www.youtube.com/shorts/AbC123xyz_-")
check("Reconoce YouTube Shorts", _sh["embed"].endswith("/embed/AbC123xyz_-"))
_ig = millca.clasificar_video("https://www.instagram.com/reel/C9xYz12AbCd/?igsh=1")
check("Reconoce reels de Instagram y AVISA su límite",
      _ig["plataforma"] == "instagram" and "/reel/C9xYz12AbCd/embed/" in _ig["embed"]
      and "públicas" in _ig["aviso"])
check("Un enlace de otra plataforma no se incrusta: queda como enlace",
      millca.clasificar_video("https://vimeo.com/123")["embed"] == "")
_urls_fabrica = [v["url"] for v in millca.PARAMS_DEFECTO["videos"]]
check("Los videos de fábrica son los entregados por Alberto (3 reels + 2 YouTube)",
      len(_urls_fabrica) == 5
      and sum("instagram.com/reel/" in u for u in _urls_fabrica) == 3
      and sum("youtu.be/" in u for u in _urls_fabrica) == 2,
      f"hay {_urls_fabrica}")
check("Todos los videos de fábrica se pueden incrustar",
      all(millca.clasificar_video(u)["embed"] for u in _urls_fabrica),
      "un enlace de fábrica que no incruste rompería la demo al abrirla")
check("El perfil de Instagram es la cuenta real de Millca",
      millca.PARAMS_DEFECTO["instagram_perfil"].rstrip("/").endswith("/millcadesign"))
_home_src = (RAIZ / "src/app/Home.py").read_text(encoding="utf-8")
check("La demo NO está en los botones de la SBC",
      "_secciones = [_conversar, _biblia, _personalizar]" in _home_src
      and "_millca = [" in _home_src)
_ml_src = "".join(p.read_text(encoding="utf-8") for p in (RAIZ / "src/app/millca").glob("*.py"))
check("La demo no toca el índice ni la configuración de la SBC",
      "from nucleo import indice" not in _ml_src and "cotizador" not in _ml_src
      and "nucleo.biblia" not in _ml_src,
      "la demo tiene que vivir aislada de los documentos internos")


print("\n═══ 7-ter. NUEVO TESTAMENTO DE EJEMPLO (RV1909) ═══")
from nucleo import semilla, biblia  # noqa: E402
import re as _re3  # noqa: E402

_nt_df = semilla.nuevo_testamento()
_CANON = {"Mateo": 28, "Marcos": 16, "Lucas": 24, "Juan": 21, "Hechos": 28, "Romanos": 16,
          "1 Corintios": 16, "2 Corintios": 13, "Gálatas": 6, "Efesios": 6, "Filipenses": 4,
          "Colosenses": 4, "1 Tesalonicenses": 5, "2 Tesalonicenses": 3, "1 Timoteo": 6,
          "2 Timoteo": 4, "Tito": 3, "Filemón": 1, "Hebreos": 13, "Santiago": 5, "1 Pedro": 5,
          "2 Pedro": 3, "1 Juan": 5, "2 Juan": 1, "3 Juan": 1, "Judas": 1, "Apocalipsis": 22}
_caps_real = _nt_df.groupby("libro")["capitulo"].nunique().to_dict()
check("27 libros y los capítulos de cada uno iguales al canon (260)",
      _caps_real == _CANON, f"diferencias: { {k: (_caps_real.get(k), v) for k, v in _CANON.items() if _caps_real.get(k) != v} }")
check("7.955 versículos con texto (2 Co 13:14 y Hch 19:41 vienen dentro del anterior)",
      len(_nt_df) == 7955
      and int(_nt_df[_nt_df["libro"] == "2 Corintios"]["versiculo"][_nt_df["capitulo"] == 13].max()) == 13
      and int(_nt_df[_nt_df["libro"] == "Hechos"]["versiculo"][_nt_df["capitulo"] == 19].max()) == 40,
      f"hay {len(_nt_df)}")
check("Ningún versículo vacío ni con restos de marcado",
      not _nt_df["texto"].astype(str).str.strip().eq("").any()
      and not _nt_df["texto"].astype(str).str.contains(r"[<>]|[GH]\d{3,}", regex=True).any())
check("Sin las 14 notas finales de las epístolas (no son texto bíblico)",
      not _nt_df["texto"].astype(str).str.contains(
          r"fué escrita|Escrita de|Enviada de|fué enviada", regex=True).any(),
      "el archivo fuente pegaba 'Fué escrita de Corinto…' dentro del último versículo")
check("Romanos 16:27 termina en 'Amén.'",
      _nt_df[(_nt_df["libro"] == "Romanos") & (_nt_df["capitulo"] == 16)
             & (_nt_df["versiculo"] == 27)]["texto"].iloc[0].endswith("para siempre. Amén."))
check("Cada libro tiene un único número de orden, de 40 (Mateo) a 66 (Apocalipsis)",
      sorted(_nt_df.groupby("libro")["orden"].first().tolist()) == list(range(40, 67))
      and _nt_df.groupby("libro")["orden"].nunique().max() == 1)
check("Filipenses 4:13 es el de 1909",
      _nt_df[(_nt_df["libro"] == "Filipenses") & (_nt_df["capitulo"] == 4)
             & (_nt_df["versiculo"] == 13)]["texto"].iloc[0]
      == "Todo lo puedo en Cristo que me fortalece.")

check("Sin texto oficial cargado, la Biblia muestra el ejemplo y lo sabe",
      biblia.es_ejemplo() and len(biblia.leer_corpus()) == 7955
      and biblia.resumen()["es_ejemplo"] is True)
_ant, _sig = biblia.vecinos("RV1909", "Mateo", 28)
check("'Siguiente' cruza de libro: después de Mateo 28 viene Marcos 1",
      _sig == ("Marcos", 1) and _ant == ("Mateo", 27))
check("Primer y último capítulo: sin anterior ni siguiente",
      biblia.vecinos("RV1909", "Mateo", 1)[0] is None
      and biblia.vecinos("RV1909", "Apocalipsis", 22)[1] is None)
_ok_b, _ = biblia.guardar_corpus(_pd.DataFrame([
    {"version": "RVR", "libro": "Juan", "orden": 43, "capitulo": 1, "versiculo": 1, "texto": "x"}]))
check("Al cargar un texto oficial, el ejemplo deja de mostrarse",
      _ok_b and not biblia.es_ejemplo() and biblia.versiones() == ["RVR"])
biblia.RUTA_BIBLIA.unlink(missing_ok=True)
check("Si se retira el oficial, vuelve el ejemplo", biblia.es_ejemplo())

print("\n═══ 7-quater. NUBE: MEMORIA DE LO QUE NO EXISTE ═══")
# Se carga una copia AISLADA de nube.py (la de arriba está intervenida para
# no tocar la red) y se le pone un 'requests' falso que cuenta llamadas.
import importlib.util as _iu  # noqa: E402
_spec = _iu.spec_from_file_location("nube_aislada", RAIZ / "src/nucleo/nube.py")
_nube = _iu.module_from_spec(_spec); _spec.loader.exec_module(_nube)
_llamadas = {"get": 0}

class _Resp:
    def __init__(self, code): self.status_code, self.content = code, b"x"

class _ReqFalso:
    class exceptions: Timeout = TimeoutError
    estado_get = 400
    @staticmethod
    def get(*a, **k):
        _llamadas["get"] += 1
        if _ReqFalso.estado_get == "error":
            raise ConnectionError("red caída")
        return _Resp(_ReqFalso.estado_get)
    @staticmethod
    def post(*a, **k): return _Resp(200)

_nube.requests = _ReqFalso
_nube._config = lambda: {"url": "https://x", "key": "k", "bucket": "b"}
for _ in range(6):
    _nube.bajar_bytes("estado/biblia.parquet")
check("Un archivo que no existe se consulta UNA vez, no en cada toque",
      _llamadas["get"] == 1, f"hubo {_llamadas['get']} consultas para 6 lecturas")
_nube.subir_bytes("estado/biblia.parquet", b"x")
_nube.bajar_bytes("estado/biblia.parquet")
check("Subir el archivo borra el recuerdo: la siguiente lectura sí consulta",
      _llamadas["get"] == 2)
_llamadas["get"] = 0; _ReqFalso.estado_get = "error"
for _ in range(3):
    _nube.bajar_bytes("estado/otro.json")
check("Un error de RED no se recuerda como 'no existe' (puede ser pasajero)",
      _llamadas["get"] == 3,
      "dar por inexistente un archivo que sí existe es el patrón que borró histórico")

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
          for n in ("conversar.py", "biblia.py", "personalizar.py",
                    "administrar.py")))
_home = (RAIZ / "src/app/Home.py").read_text(encoding="utf-8")
check("La navegación va abajo, no en el panel lateral",
      'position="hidden"' in _home and "barra_inferior" in _home,
      "el menú lateral obliga a tocar la esquina más lejos del pulgar")
_publicas = ["conversar.py", "biblia.py", "personalizar.py"]
check("Ninguna pantalla pública pide clave",
      all("solo_admin()" not in (RAIZ / "src/app/paginas" / n).read_text(encoding="utf-8")
          for n in _publicas),
      "la app se usa sin clave; la clave es solo para administrar")
check("La pantalla de administración SÍ pide clave",
      "solo_admin()" in (RAIZ / "src/app/paginas/administrar.py").read_text(encoding="utf-8"))
_css = (RAIZ / "src/app/ui.py").read_text(encoding="utf-8")
# La barra se apilaba en vertical en el celular: Streamlit pone las
# columnas una debajo de otra cuando la pantalla es angosta, que es
# justo el caso de uso de esta app.
_bloque_barra = _css[_css.index(".st-key-barra_inferior [data-testid=\"stHorizontalBlock\"]"):] \
    if ".st-key-barra_inferior [data-testid=\"stHorizontalBlock\"]" in _css else ""
check("La barra inferior se mantiene en UNA fila en pantallas angostas",
      "flex-direction: row !important" in _bloque_barra
      and "flex-wrap: nowrap !important" in _bloque_barra,
      "sin esto, en el celular los botones se apilan y ocupan media pantalla")
# La piel de Millca ahora genera el CSS por paleta: se evalúa el CSS
# RESULTANTE de cada tema, no el texto del archivo.
import app.millca.estilo as _ml_estilo  # noqa: E402
_css_ml_por_tema = {k: _ml_estilo._css(pal) for k, pal in _ml_estilo.PALETAS.items()}
_css_ml = "\n".join(_css_ml_por_tema.values())
check("Las barras fijas tienen un fondo REAL (no una variable inexistente)",
      "var(--background-color)" not in _css and "var(--background-color)" not in _css_ml
      and "background: canvas;" in _css
      and all(f'background: {pal["fondo"]};' in _css_ml_por_tema[k]
              for k, pal in _ml_estilo.PALETAS.items()),
      "con var(--background-color) la barra quedaba transparente y el texto "
      "se leía por debajo; pasó en producción en la v2.1")
check("La barra de Millca deja libre la esquina del distintivo de Streamlit Cloud",
      all(f"right: {_ml_estilo._RESERVA_BADGE}px;" in c
          and "width: auto !important;" in c[c.index(".st-key-ml_barra {"):]
          for c in _css_ml_por_tema.values())
      and _ml_estilo._RESERVA_BADGE >= 100,
      "el distintivo lo pinta la plataforma por fuera de la app y tapaba la "
      "tercera pestaña en el celular")
check("Cada paleta pinta el fondo de TODA la app, no solo las tarjetas",
      all('.stApp, [data-testid="stAppViewContainer"]' in c for c in _css_ml_por_tema.values()),
      "un modo oscuro de tarjetas sobre fondo blanco no es un modo oscuro")
_src_estilo = (RAIZ / "src/app/millca/estilo.py").read_text(encoding="utf-8")
check("El tema elegido se guarda en la URL, no solo en la sesión",
      "st.query_params" in _src_estilo and 'PARAM_TEMA = "tema"' in _src_estilo,
      "la sesión de Streamlit se renueva al refrescar: el modo oscuro duraba "
      "hasta el primer refresco")
check("La demo ya no usa el deslizador de Streamlit (quedaba rojo)",
      "select_slider" not in (RAIZ / "src/app/millca/palabra.py").read_text(encoding="utf-8")
      and "stSlider" not in _src_estilo)
check("El modo oscuro de Millca no es el claro con otro nombre",
      _ml_estilo.PALETAS["claro"]["fondo"] != _ml_estilo.PALETAS["oscuro"]["fondo"]
      and _ml_estilo.PALETAS["claro"]["texto"] != _ml_estilo.PALETAS["oscuro"]["texto"])
check("Se oculta el botón Deploy de Streamlit",
      "stAppDeployButton" in _css and "stAppDeployButton" in _css_ml,
      "un botón 'Deploy' arriba a la derecha delata la herramienta")
check("Las columnas de la barra se reparten el ancho por igual",
      "flex: 1 1 0 !important" in _css and "min-width: 0 !important" in _css,
      "sin min-width:0 un nombre largo empuja a los demás fuera de la barra")

# Pedido explícito: nada de iconos en la interfaz.
import re as _re  # noqa: E402
_EMOJI = _re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")
_con_emoji = [p.name for p in (RAIZ / "src/app").rglob("*.py")
              if _EMOJI.search(p.read_text(encoding="utf-8"))]
check("La interfaz no usa iconos ni emojis",
      not _con_emoji, f"quedaron en: {_con_emoji}")

_home_txt = (RAIZ / "src/app/Home.py").read_text(encoding="utf-8")
check("Abajo hay exactamente TRES secciones",
      "_secciones = [_conversar, _biblia, _personalizar]" in _home_txt,
      "una cuarta opción compite con lo que la gente vino a hacer")
check("La configuración no ocupa un lugar en la barra, pero es alcanzable",
      "acceso_tope(_administrar" in _home_txt
      and "_secciones + [_administrar]" in _home_txt,
      "tiene que estar registrada como página aunque no esté en la barra")

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

# ── Acceso de administrador ──────────────────────────────────────────
import tomllib as _toml  # noqa: E402
_ej = _toml.loads((RAIZ / ".streamlit/secrets.toml.ejemplo").read_text(encoding="utf-8"))
check("El ejemplo de Secrets produce [usuarios] con el administrador ADENTRO",
      "usuarios" in _ej and "director.promocion@sbcol.org" in _ej["usuarios"]
      and _ej["usuarios"]["director.promocion@sbcol.org"].get("rol") == "admin"
      and not any(str(k).startswith("usuarios.") for k in _ej),
      "en la v2.0 se documentó ['usuarios.NOMBRE'], que crea otra sección: nadie podía entrar")
# Ninguna clave real en el repositorio. El check NO conoce la clave (si la
# tuviera escrita, la estaría publicando): busca cualquier línea de estilo
# TOML  clave = "…"  cuyo valor no sea uno de los marcadores de ejemplo.
_MARCADORES = {"PEGAR_AQUI_LA_CLAVE", "TU_CLAVE", "CAMBIAR", "CAMBIAR_POR_UNA_CLAVE_LARGA",
               "LA_MISMA_CLAVE_DE_SIEMPRE", "cambiar-en-secrets", "...", ""}
_con_clave = []
for _f in RAIZ.rglob("*"):
    if not _f.is_file() or ".git" in _f.parts or _f.name == "auditoria_iasbc.py" or _f.suffix not in (
            ".py", ".md", ".toml", ".txt", ".ejemplo", ".ipynb", ".json", ".bat", ".command"):
        continue
    for _v in _re3.findall(r'clave\s*=\s*\\?["\']([^"\'\\]*)\\?["\']',
                           _f.read_text(encoding="utf-8", errors="ignore")):
        if _v.strip() not in _MARCADORES:
            _con_clave.append(f"{_f.relative_to(RAIZ)}: {_v[:2]}…")
check("Ninguna clave real escrita en el repositorio (solo marcadores de ejemplo)",
      not _con_clave, f"revisá: {_con_clave}")
check("No hay un secrets.toml real dentro del repositorio",
      not (RAIZ / ".streamlit/secrets.toml").exists())
_estado_src = (RAIZ / "src/app/estado.py").read_text(encoding="utf-8")
check("Solo entra quien tenga rol 'admin' (antes entraba cualquier usuario)",
      'usuarios[match].get("rol") == ROL_ADMIN' in _estado_src)
check("El usuario de fábrica NO vale en la nube (solo sin ningún secreto)",
      "return {} if _secretos_existen() else dict(USUARIOS_DEFECTO)" in _estado_src,
      "hasta la v2.2 'admin / cambiar-en-secrets' abría la configuración en la nube")
check("La clave se compara en tiempo constante y un fallo hace esperar",
      "hmac.compare_digest" in _estado_src and "time.sleep(PAUSA_INTENTO_FALLIDO)" in _estado_src)
check("El formulario no muestra el nombre del administrador como ejemplo",
      "PEÑA JOSE ALBERTO" not in _estado_src.split("def solo_admin")[1])
_bloque_acc = _css[_css.index(".st-key-acceso_tope {"):_css.index(".st-key-acceso_tope .stButton")]
check("El botón Entrar está en la esquina superior IZQUIERDA",
      "left: 0.9rem;" in _bloque_acc and "right:" not in _bloque_acc)
import app.ui as _ui_mod  # noqa: E402
_css_sbc = _ui_mod._CSS                      # el estilo YA armado, como llega al navegador
_bloque_barra_sbc = _css_sbc[_css_sbc.index(".st-key-barra_inferior {"):]
_bloque_barra_sbc = _bloque_barra_sbc[:_bloque_barra_sbc.index("}")]
check("La barra de la SBC deja libre la esquina del distintivo de Streamlit Cloud",
      f"right: {_ui_mod._RESERVA_BADGE}px;" in _bloque_barra_sbc
      and _ui_mod._RESERVA_BADGE >= 100
      and "width: auto !important;" in _bloque_barra_sbc
      and "bottom: 0;" in _bloque_barra_sbc
      and "_ALTO_BADGE" not in (RAIZ / "src/app/ui.py").read_text(encoding="utf-8"),
      "la versión a medias levantaba la barra y dejaba ver el texto por debajo")
_multis = [(f.name, m) for f in (RAIZ / "src/app").rglob("*.py")
           for m in _re3.findall(r"st\.multiselect\((?:[^()]|\([^()]*\))*\)",
                                 f.read_text(encoding="utf-8"))]
check("Todo selector múltiple trae su texto en español (Streamlit pone 'Choose options')",
      all("placeholder=" in m for _, m in _multis),
      f"sin placeholder: {[n for n, m in _multis if 'placeholder=' not in m]}")
_regla_prim = _css_sbc[_css_sbc.index('.stButton > button[kind="primary"],'):]
_regla_prim = _regla_prim[:_regla_prim.index("}")]
check("La regla general de botones NO usa !important (aplastaba la pestaña activa de la barra)",
      "!important" not in _regla_prim,
      "con !important la pestaña activa quedaba azul sobre azul, sin texto visible")
check("El botón de enviar un formulario (el 'Entrar') usa el azul institucional",
      'button[kind="primaryFormSubmit"]' in _css_sbc,
      "salía con el rojo por defecto de Streamlit")
check("La extracción del Nuevo Testamento viaja con el código (procedencia)",
      (RAIZ / "herramientas/extraer_nt_rv1909.py").exists())
_datos_prohibidos = [p for p in (RAIZ / "data").rglob("*") if p.is_file()
                     and p.name != ".gitkeep" and "semilla" not in p.parts]
check("El repositorio viaja sin datos de la SBC",
      not _datos_prohibidos,
      f"data/documentos y data/estado deben ir vacíos: {_datos_prohibidos}")
check("En data/semilla solo viajan el NT de dominio público y la lista SIMULADA",
      sorted(p.name for p in (RAIZ / "data/semilla").glob("*"))
      == ["nt_rv1909.csv", "precios_simulados.xlsx"],
      "data/semilla es solo para la RV1909; nada de la SBC va ahí")

# ── Color de acento por modo (v2.3) ──────────────────────────────────
# Nació del borde ROJO de cada campo al tocarlo (el acento de fábrica de
# Streamlit). [theme] a secas forzaría el modo claro; [theme.light] y
# [theme.dark] respetan la preferencia del sistema (verificado en un
# navegador con Streamlit 1.57.0, en los dos modos).
import tomllib as _tomllib  # noqa: E402
from nucleo.config import COLOR_PRIMARIO as _CP, COLOR_PRIMARIO_OSCURO as _CPO  # noqa: E402

_tema = _tomllib.loads((RAIZ / ".streamlit/config.toml").read_text(encoding="utf-8")).get("theme", {})
check("El tema solo define el acento de cada modo ([theme.light] y [theme.dark])",
      set(_tema) == {"light", "dark"}
      and all(isinstance(_tema[m], dict) and set(_tema[m]) == {"primaryColor"}
              for m in ("light", "dark")),
      f"claves en [theme]: {sorted(_tema)} — cualquier otra (base, fondo…) puede "
      "forzar un modo para todos")
check("El acento del tema es el azul de la SBC en los dos modos (config.toml = nucleo/config.py)",
      str(_tema.get("light", {}).get("primaryColor", "")).lower() == _CP.lower()
      and str(_tema.get("dark", {}).get("primaryColor", "")).lower() == _CPO.lower(),
      "si no coinciden, la app muestra dos azules distintos")


def _luminancia(h: str) -> float:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(a: str, b: str) -> float:
    x, y = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


_FONDO_OSCURO = "#0e1117"                     # el fondo del modo oscuro de Streamlit
check("El acento del modo oscuro se lee sobre el fondo oscuro (contraste ≥ 4,5:1)",
      _contraste(_CPO, _FONDO_OSCURO) >= 4.5,
      f"contraste {_contraste(_CPO, _FONDO_OSCURO):.2f}:1")
_media_osc = (_css_sbc[_css_sbc.index("@media (prefers-color-scheme: dark)"):]
              if "@media (prefers-color-scheme: dark)" in _css_sbc else "")
check("En modo oscuro la pestaña activa de la barra usa el azul aclarado",
      '.st-key-barra_inferior .stButton > button[kind="primary"]' in _media_osc[:400]
      and f"color: {_CPO};" in _media_osc[:400],
      f"el azul institucional sobre el fondo oscuro tiene contraste "
      f"{_contraste(_CP, _FONDO_OSCURO):.2f}:1: la pestaña activa casi no se leía")
check("Los botones principales siguen en el azul oscuro: texto blanco legible en los dos modos",
      f"background-color: {_CP};" in _regla_prim and _contraste("#ffffff", _CP) >= 4.5,
      "con el acento claro del modo oscuro, el texto blanco quedaría en 2,5:1")
check("En la demo Millca el borde de un campo al tocarlo es rosa, no el azul de la SBC",
      all('[data-testid="stTextAreaRootElement"]:focus-within' in c
          and f'border-color: {_ml_estilo.PALETAS[k]["rosa"]} !important;' in c
          for k, c in _css_ml_por_tema.items()),
      "la demo tiene que verse como la app de Millca, no como la de la SBC")
check("Streamlit sigue fijo en la 1.57.0, la versión en que se verificó la piel en un navegador",
      "streamlit==1.57.0" in (RAIZ / "requirements.txt").read_text(encoding="utf-8"),
      "en la 1.66 cambian los selectores del selectbox y de las pestañas que usa la piel "
      "de Millca: subir de versión exige revisarla primero")

# ── Al cambiar de capítulo, la pantalla va a su comienzo (v2.3) ──────
# Los botones están al final del texto: sin esto, el capítulo nuevo se
# abría mostrando su FINAL y había que subir a mano en cada capítulo.
_src_bib = (RAIZ / "src/app/paginas/biblia.py").read_text(encoding="utf-8")
_src_pal = (RAIZ / "src/app/millca/palabra.py").read_text(encoding="utf-8")
_src_ui = (RAIZ / "src/app/ui.py").read_text(encoding="utf-8")


def _ultima_linea(txt: str) -> str:
    return [l.strip() for l in txt.splitlines() if l.strip()][-1]


check("Las dos Biblias llevan la pantalla al comienzo del capítulo nuevo, y el ancla existe",
      'llevar_a(".st-key-bib_capitulo"' in _src_bib and 'key="bib_capitulo"' in _src_bib
      and 'llevar_a(".ml-lectura"' in _src_pal and 'class="ml-lectura"' in _src_pal,
      "si el ancla no existe, el script lleva arriba del todo en vez de al capítulo")
check("El salto va al FINAL de cada página (cuando corre, el capítulo ya está dibujado)",
      _ultima_linea(_src_bib).startswith("llevar_a(")
      and _ultima_linea(_src_pal).startswith("llevar_a("))
check("El salto no depende de la etiqueta del contenedor de Streamlit",
      "section[data-testid" not in _src_ui and "unsafe_allow_javascript=True" in _src_ui,
      "en la 1.57 el contenedor que se desplaza es <section> y en la 1.66 <main>")

print("\n" + "═" * 60)
if _FALLOS:
    print(f"RESULTADO: {_OK} checks OK · {len(_FALLOS)} FALLAS\n")
    for f in _FALLOS:
        print(f"  ✗ {f}")
    sys.exit(1)
print(f"RESULTADO: {_OK} checks OK · sin fallas")
