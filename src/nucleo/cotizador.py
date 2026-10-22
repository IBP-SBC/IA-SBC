"""
nucleo/cotizador.py
===================
Cotización de producto personalizado: Biblias, Nuevos Testamentos,
Evangelios, tratados y producto propio del cliente.

LA REGLA QUE ORDENA TODO ESTE MÓDULO: **los precios no se inventan.**
No hay una sola cifra escrita en este código. El precio sale de una tabla
que carga el área comercial, con la misma lógica de las plantillas de
sbc_ventas. Si la tabla no está cargada, la app lo dice y ofrece pedir
cotización sin precio — nunca muestra un número "de referencia".

LO QUE LA COTIZACIÓN TIENE QUE DECIR SIEMPRE, aunque incomode:
  · el MÍNIMO de producción. Una Biblia con el logo de una iglesia se
    fabrica en la planta propia: se monta una corrida completa. Cotizar
    50 unidades y que comercial tenga que desdecirse después es peor que
    decirlo de entrada.
  · el TIEMPO de entrega real, que no es el de un producto de catálogo.
  · que el valor es una ESTIMACIÓN sujeta a confirmación comercial: el
    cliente tiene que saber qué está mirando.

FORMATO DE LA TABLA DE PRECIOS (una fila por combinación cotizable):
  familia        Biblia | Nuevo Testamento | Evangelio | Tratado | Producto propio
  referencia     nombre comercial de la configuración
  version        RVR | TLA | (vacío si no aplica)
  tamano         13x21 agenda, etc.
  cubierta       Imitación piel, etc.
  desde_cantidad entero: desde cuántas unidades aplica este precio
  precio_unitario  COP por unidad, sin separadores de miles
  minimo         entero: mínimo de producción de esa familia
  dias_entrega   entero: días hábiles
  incluye        texto libre de lo que cubre el precio
Y una tabla aparte, opcional, de ADICIONALES (logo, grabado, inserto):
  concepto · tipo (unitario|fijo) · valor · aplica_a (familia o 'todas')
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from nucleo import nube
from nucleo.config import ESTADO_DIR, ROOT
from nucleo.util import sello_ahora

ARCHIVO_PRECIOS = "precios.parquet"
ARCHIVO_ADICIONALES = "precios_adicionales.parquet"
ARCHIVO_PARAMS = "cotizador.json"

RUTA_PRECIOS = ESTADO_DIR / ARCHIVO_PRECIOS
RUTA_ADICIONALES = ESTADO_DIR / ARCHIVO_ADICIONALES

# Lista SIMULADA para probar el cotizador. Viaja en el repo; no es la
# lista oficial y la app lo anuncia mientras esté activa.
RUTA_LISTA_PRUEBA = ROOT / "data" / "semilla" / "precios_simulados.xlsx"

# Nombres de columna: fuente única. Cualquier módulo los IMPORTA en vez de
# escribirlos sueltos (la lección de los nombres de materias primas).
COLS_PRECIOS = ["familia", "referencia", "version", "tamano", "cubierta",
                "desde_cantidad", "precio_unitario", "minimo", "dias_entrega",
                "incluye"]
COLS_ADICIONALES = ["concepto", "tipo", "valor", "aplica_a"]

FAMILIAS = ["Biblia", "Nuevo Testamento", "Evangelio", "Tratado",
            "Producto propio"]


# ════════════════════════════════════════════════════════════════════
# CARGA Y LECTURA DE LA TABLA
# ════════════════════════════════════════════════════════════════════

def _leer(ruta: Path, clave: str, columnas: list[str]) -> pd.DataFrame:
    """Lee una tabla de estado; si falta en disco, la busca en la nube."""
    if not ruta.exists():
        nube.bajar_archivo(nube.clave_estado(clave), ruta)
    if not ruta.exists():
        return pd.DataFrame(columns=columnas)
    try:
        df = pd.read_parquet(ruta)
    except Exception:
        return pd.DataFrame(columns=columnas)
    faltan = [c for c in columnas if c not in df.columns]
    return pd.DataFrame(columns=columnas) if faltan else df


def leer_precios() -> pd.DataFrame:
    return _leer(RUTA_PRECIOS, ARCHIVO_PRECIOS, COLS_PRECIOS)


def leer_adicionales() -> pd.DataFrame:
    return _leer(RUTA_ADICIONALES, ARCHIVO_ADICIONALES, COLS_ADICIONALES)


def hay_precios() -> bool:
    return not leer_precios().empty


TIPOS_ADICIONAL = ("unitario", "fijo")


def _validar_adicionales(adic: pd.DataFrame) -> tuple[pd.DataFrame | None, str]:
    """
    Valida la hoja de agregados. Devuelve (tabla limpia, "") o (None, error).

    Hasta la v2.2 un valor escrito como texto ("$1.500") se volvía $0 sin
    aviso, y una hoja con columnas faltantes se ignoraba: el cliente veía
    una cotización sin el agregado que pidió.
    """
    adic = adic.copy()
    adic.columns = [str(c).strip().lower() for c in adic.columns]
    faltan = [c for c in COLS_ADICIONALES if c not in adic.columns]
    if faltan:
        return None, "A la hoja 'adicionales' le faltan columnas: " + ", ".join(faltan)
    adic = adic[COLS_ADICIONALES].dropna(how="all")
    adic["concepto"] = adic["concepto"].astype(str).str.strip()
    adic["tipo"] = adic["tipo"].astype(str).str.strip().str.lower()
    adic["aplica_a"] = adic["aplica_a"].fillna("todas").astype(str).str.strip()
    adic.loc[adic["aplica_a"] == "", "aplica_a"] = "todas"
    adic["valor"] = pd.to_numeric(adic["valor"], errors="coerce")
    malos_tipo = adic[~adic["tipo"].isin(TIPOS_ADICIONAL)]
    if not malos_tipo.empty:
        return None, (f"En 'adicionales', el tipo tiene que ser 'unitario' o 'fijo'. "
                      f"Revisá: {', '.join(malos_tipo['concepto'].head(5))}.")
    malos_valor = adic[adic["valor"].isna() | (adic["valor"] < 0)]
    if not malos_valor.empty:
        return None, (f"En 'adicionales' hay valores que no son un número válido "
                      f"(sin '$' ni puntos de miles): "
                      f"{', '.join(malos_valor['concepto'].head(5))}.")
    clave = adic["concepto"].str.lower() + "|" + adic["aplica_a"].str.lower()
    if clave.duplicated().any():
        repetidos = adic.loc[clave.duplicated(keep=False), "concepto"].unique()
        return None, ("En 'adicionales' hay conceptos repetidos para la misma "
                      f"familia: {', '.join(repetidos[:5])}. Debe haber uno solo.")
    return adic.reset_index(drop=True), ""


def cargar_tabla(datos: bytes, nombre_archivo: str, usuario: str,
                 simulada: bool = False) -> tuple[bool, str]:
    """
    Carga la lista de precios (hoja 'precios') y sus agregados (hoja
    'adicionales') desde un Excel, o solo los precios desde un CSV.

    TODO O NADA: se valida todo antes de escribir. Una lista mal cargada no
    rompe la app: cotiza mal, que es peor, porque nadie se da cuenta hasta
    que el cliente reclama.

    Cargar una lista REEMPLAZA también sus agregados. Si la lista nueva no
    trae hoja de agregados, los anteriores se borran: los agregados son
    parte de la lista, y los de una lista de prueba no pueden sobrevivir a
    la oficial.

    simulada=True marca la lista como DE PRUEBA: la pantalla pública lo
    anuncia y la solicitud que se envía lo dice en la primera línea.
    """
    ext = Path(nombre_archivo).suffix.lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            hojas = pd.read_excel(io.BytesIO(datos), sheet_name=None)
            df = hojas.get("precios", list(hojas.values())[0])
            adic = hojas.get("adicionales")
        elif ext == ".csv":
            df = pd.read_csv(io.BytesIO(datos), sep=None, engine="python")
            adic = None
        else:
            return False, f"No sé leer '{ext}'. Usá .xlsx o .csv."
    except Exception as e:
        return False, f"No se pudo abrir el archivo: {e}"

    df.columns = [str(c).strip().lower() for c in df.columns]
    faltan = [c for c in COLS_PRECIOS if c not in df.columns]
    if faltan:
        return False, ("A la tabla le faltan columnas: " + ", ".join(faltan)
                       + ". Descargá la plantilla y llenala sin cambiar los "
                         "encabezados.")
    df = df[COLS_PRECIOS].dropna(how="all").copy()

    # Tipos: los precios y cantidades tienen que ser números de verdad.
    for col in ("desde_cantidad", "precio_unitario", "minimo", "dias_entrega"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    malas = df[df[["desde_cantidad", "precio_unitario", "minimo"]].isna().any(axis=1)]
    if not malas.empty:
        return False, (f"{len(malas)} fila(s) tienen cantidad o precio que no "
                       "es un número. Revisá que no haya '$', puntos de miles "
                       "ni celdas vacías.")
    if (df["precio_unitario"] <= 0).any():
        return False, "Hay precios en cero o negativos. Corregí la tabla."

    adic_limpia = pd.DataFrame(columns=COLS_ADICIONALES)
    if adic is not None and not adic.dropna(how="all").empty:
        adic_limpia, error = _validar_adicionales(adic)
        if adic_limpia is None:
            return False, error + " No se guardó nada."

    # ── Escritura: precios y agregados juntos ───────────────────────
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RUTA_PRECIOS, index=False)
    ok = nube.subir_archivo(RUTA_PRECIOS, nube.clave_estado(ARCHIVO_PRECIOS))
    if adic_limpia.empty:
        RUTA_ADICIONALES.unlink(missing_ok=True)
        nube.eliminar(nube.clave_estado(ARCHIVO_ADICIONALES))
    else:
        adic_limpia.to_parquet(RUTA_ADICIONALES, index=False)
        ok = nube.subir_archivo(RUTA_ADICIONALES,
                                nube.clave_estado(ARCHIVO_ADICIONALES)) and ok

    guardar_parametros({"ultima_carga": sello_ahora(), "usuario": usuario,
                        "filas": int(len(df)), "simulada": bool(simulada)})
    tipo = "de PRUEBA" if simulada else "oficial"
    msg_adic = (f" y {len(adic_limpia)} agregado(s)" if not adic_limpia.empty
                else " (sin agregados)")
    estado_nube = "" if ok else " OJO: no se pudo respaldar en la nube."
    return True, (f"Lista {tipo} cargada: {len(df)} combinaciones de precio"
                  f"{msg_adic}." + estado_nube)


def borrar_lista() -> str:
    """
    Quita la lista activa (precios y agregados). Se usa para retirar la
    lista de prueba; la oficial se reemplaza cargando otra, no se borra.
    """
    for ruta, archivo in ((RUTA_PRECIOS, ARCHIVO_PRECIOS),
                          (RUTA_ADICIONALES, ARCHIVO_ADICIONALES)):
        ruta.unlink(missing_ok=True)
        nube.eliminar(nube.clave_estado(archivo))
    guardar_parametros({"simulada": False, "filas": 0})
    return "Lista retirada. El cotizador vuelve a enviar solicitudes sin precio."


def es_simulada() -> bool:
    """True si la lista activa es la de prueba."""
    return bool(leer_parametros().get("simulada")) and hay_precios()


def cargar_lista_de_prueba(usuario: str) -> tuple[bool, str]:
    """
    Carga la lista SIMULADA que viaja en el repositorio, por el mismo camino
    y con la misma validación que una lista real.
    """
    if not RUTA_LISTA_PRUEBA.exists():
        return False, f"No encuentro la lista de prueba ({RUTA_LISTA_PRUEBA.name})."
    return cargar_tabla(RUTA_LISTA_PRUEBA.read_bytes(), RUTA_LISTA_PRUEBA.name,
                        usuario, simulada=True)


def plantilla_csv() -> bytes:
    """
    Plantilla vacía con los encabezados y UNA fila de ejemplo marcada
    como tal. La fila de ejemplo lleva precios en cero a propósito: si
    alguien la olvida adentro, la validación la rechaza en vez de
    dejarla pasar como si fuera un precio real.
    """
    ejemplo = (
        "Biblia,EJEMPLO - BORRAR ESTA FILA,RVR,13x21 agenda,Imitación piel,"
        "800,0,800,90,Personalización de cubierta con logo y nombre\n")
    return (",".join(COLS_PRECIOS) + "\n" + ejemplo).encode("utf-8")


# ── Parámetros del cotizador (contacto, textos) ─────────────────────

def leer_parametros() -> dict:
    datos = nube.leer_json_remoto(ARCHIVO_PARAMS)
    if datos is None:
        ruta = ESTADO_DIR / ARCHIVO_PARAMS
        if ruta.exists():
            try:
                return json.loads(ruta.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    return datos


def guardar_parametros(cambios: dict) -> None:
    params = leer_parametros()
    params.update(cambios)
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    (ESTADO_DIR / ARCHIVO_PARAMS).write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    nube.subir_bytes(nube.clave_estado(ARCHIVO_PARAMS),
                     json.dumps(params, ensure_ascii=False).encode("utf-8"))


# ════════════════════════════════════════════════════════════════════
# CÁLCULO
# ════════════════════════════════════════════════════════════════════

def opciones(campo: str, filtros: dict | None = None) -> list[str]:
    """
    Valores disponibles de un campo, respetando lo ya elegido. Así el
    formulario nunca ofrece una combinación que no existe en la tabla.
    """
    df = leer_precios()
    if df.empty or campo not in df.columns:
        return []
    for k, v in (filtros or {}).items():
        if v and k in df.columns:
            df = df[df[k].astype(str) == str(v)]
    valores = [str(v) for v in df[campo].dropna().unique() if str(v).strip()]
    return sorted(valores)


def _aplica(aplica_a, familia: str) -> bool:
    a = str(aplica_a if aplica_a is not None else "todas").strip().lower()
    return a in ("todas", "", "nan", str(familia).strip().lower())


def adicionales_para(familia: str) -> list[str]:
    """Agregados que se pueden pedir para esa familia (los demás no se ofrecen)."""
    tabla = leer_adicionales()
    if tabla.empty:
        return []
    mask = tabla["aplica_a"].map(lambda a: _aplica(a, familia))
    return sorted(tabla.loc[mask, "concepto"].astype(str).unique())


def minimo_de(familia: str) -> int | None:
    """Mínimo de producción de la familia según la lista; None si no hay filas."""
    df = leer_precios()
    if df.empty:
        return None
    sel = df[df["familia"].astype(str) == str(familia)]
    if sel.empty:
        return None
    return int(pd.to_numeric(sel["minimo"], errors="coerce").min())


def cotizar(familia: str, cantidad: int, seleccion: dict,
            adicionales: list[str] | None = None) -> dict:
    """
    Calcula el valor de una cotización.

    Devuelve SIEMPRE un diccionario con 'ok' y 'mensaje'. Cuando no se
    puede calcular, dice por qué en palabras que el cliente entiende, y
    nunca devuelve un número aproximado para salir del paso.

    La escala de precio se elige por 'desde_cantidad': se toma la fila con
    el mayor 'desde_cantidad' que no supere la cantidad pedida. Es como se
    leen las listas de precios por volumen.
    """
    df = leer_precios()
    if df.empty:
        return {"ok": False, "motivo": "sin_tabla",
                "mensaje": ("Todavía no hay lista de precios cargada, así que "
                            "no puedo calcular el valor. Podés enviar la "
                            "solicitud y comercial te responde con el precio.")}

    filtro = df[df["familia"].astype(str) == str(familia)]
    if filtro.empty:
        return {"ok": False, "motivo": "a_pedido",
                "mensaje": (f"{familia}: se cotiza a pedido. Contanos en las notas "
                            "qué querés imprimir (tamaño, páginas, acabados) y "
                            "comercial te responde con el precio.")}
    for campo, valor in (seleccion or {}).items():
        if valor and campo in filtro.columns:
            filtro = filtro[filtro[campo].astype(str) == str(valor)]
    if filtro.empty:
        return {"ok": False, "motivo": "sin_combinacion",
                "mensaje": ("Esa combinación no está en la lista de precios. "
                            "Se puede cotizar a pedido: enviá la solicitud y "
                            "comercial la revisa.")}

    minimo = int(pd.to_numeric(filtro["minimo"], errors="coerce").min() or 0)
    if cantidad < minimo:
        return {"ok": False, "motivo": "bajo_minimo", "minimo": minimo,
                "mensaje": (f"La producción personalizada arranca en {minimo:,} "
                            "unidades, porque se monta una corrida completa en "
                            "la planta. Ajustá la cantidad o pedí que comercial "
                            "te proponga una alternativa de catálogo."
                            ).replace(",", ".")}

    escalas = filtro[pd.to_numeric(filtro["desde_cantidad"],
                                   errors="coerce") <= cantidad]
    if escalas.empty:
        return {"ok": False, "motivo": "sin_escala",
                "mensaje": ("No hay un precio definido para esa cantidad. "
                            "Enviá la solicitud y comercial la cotiza.")}
    fila = escalas.sort_values("desde_cantidad").iloc[-1]

    unitario = float(fila["precio_unitario"])
    subtotal = unitario * int(cantidad)

    # Agregados: unitarios (se multiplican) o fijos (una sola vez).
    # Se busca por concepto Y familia: hasta la v2.2 se tomaba la primera
    # fila del concepto y, si era de otra familia, el agregado desaparecía
    # de la cotización sin aviso. Un precio propio de la familia gana sobre
    # uno general ("todas"). Lo que no aplica se informa, no se esconde.
    detalle_adic, total_adic, no_aplican = [], 0.0, []
    tabla_adic = leer_adicionales()
    for concepto in (adicionales or []):
        cand = tabla_adic[tabla_adic["concepto"].astype(str) == str(concepto)] \
            if not tabla_adic.empty else tabla_adic
        propios = cand[cand["aplica_a"].astype(str).str.strip().str.lower()
                       == str(familia).strip().lower()] if not cand.empty else cand
        generales = cand[cand["aplica_a"].map(lambda a: _aplica(a, "__ninguna__"))] \
            if not cand.empty else cand
        fila_a = propios.iloc[0] if not propios.empty else (
            generales.iloc[0] if not generales.empty else None)
        if fila_a is None:
            no_aplican.append(str(concepto))
            continue
        valor = float(fila_a["valor"])
        es_unitario = str(fila_a["tipo"]).strip().lower() == "unitario"
        monto = valor * int(cantidad) if es_unitario else valor
        detalle_adic.append({"concepto": str(concepto), "monto": monto,
                             "tipo": "por unidad" if es_unitario else "una vez",
                             "valor": valor})
        total_adic += monto

    total = subtotal + total_adic
    return {
        "ok": True,
        "familia": str(familia),
        "referencia": str(fila.get("referencia", "")),
        "cantidad": int(cantidad),
        "unitario": unitario,
        "subtotal": subtotal,
        "adicionales": detalle_adic,
        "no_aplican": no_aplican,
        "total_adicionales": total_adic,
        "total": total,
        "unitario_con_adicionales": total / int(cantidad) if cantidad else 0.0,
        "minimo": minimo,
        "dias_entrega": int(pd.to_numeric(fila.get("dias_entrega"),
                                          errors="coerce") or 0),
        "incluye": str(fila.get("incluye", "")),
        "escala_desde": int(fila["desde_cantidad"]),
    }


def texto_solicitud(resultado: dict, seleccion: dict, datos_cliente: dict,
                    simulada: bool = False) -> str:
    """
    Arma el mensaje que el cliente le manda a comercial. Lleva TODO lo
    necesario para atenderlo sin volver a preguntar: qué quiere, cuánto,
    para quién y el valor estimado si se pudo calcular.
    """
    lineas = []
    if simulada:
        lineas += ["*** PRUEBA: precios de una lista simulada, NO válidos ***", ""]
    lineas += ["Solicitud de cotización · Sociedad Bíblica Colombiana", ""]
    if datos_cliente.get("iglesia"):
        lineas.append(f"Iglesia u organización: {datos_cliente['iglesia']}")
    if datos_cliente.get("nombre"):
        lineas.append(f"Contacto: {datos_cliente['nombre']}")
    if datos_cliente.get("telefono"):
        lineas.append(f"Teléfono: {datos_cliente['telefono']}")
    if datos_cliente.get("ciudad"):
        lineas.append(f"Ciudad: {datos_cliente['ciudad']}")
    lineas.append("")
    lineas.append(f"Producto: {resultado.get('familia', seleccion.get('familia', ''))}")
    for campo, valor in (seleccion or {}).items():
        if valor:
            lineas.append(f"- {campo.capitalize()}: {valor}")
    if datos_cliente.get("cantidad"):
        lineas.append(f"- Cantidad: {int(datos_cliente['cantidad']):,}"
                      .replace(",", "."))
    if resultado.get("ok"):
        lineas.append("")
        lineas.append(f"Valor estimado: {fmt_pesos(resultado['total'])} "
                      f"({fmt_pesos(resultado['unitario_con_adicionales'])} por unidad)")
        lineas.append("Sujeto a confirmación comercial.")
    if datos_cliente.get("notas"):
        lineas.append("")
        lineas.append(f"Notas: {datos_cliente['notas']}")
    lineas.append("")
    lineas.append(f"Enviado desde la app · {sello_ahora()}")
    return "\n".join(lineas)


def fmt_pesos(valor: float) -> str:
    """Formato colombiano: punto de miles, sin decimales."""
    try:
        return "$ " + f"{float(valor):,.0f}".replace(",", ".")
    except Exception:
        return "$ —"
