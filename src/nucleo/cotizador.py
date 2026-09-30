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
from nucleo.config import ESTADO_DIR
from nucleo.util import sello_ahora

ARCHIVO_PRECIOS = "precios.parquet"
ARCHIVO_ADICIONALES = "precios_adicionales.parquet"
ARCHIVO_PARAMS = "cotizador.json"

RUTA_PRECIOS = ESTADO_DIR / ARCHIVO_PRECIOS
RUTA_ADICIONALES = ESTADO_DIR / ARCHIVO_ADICIONALES

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


def cargar_tabla(datos: bytes, nombre_archivo: str,
                 usuario: str) -> tuple[bool, str]:
    """
    Carga la tabla de precios desde un Excel o CSV.

    Valida ANTES de guardar: columnas, tipos y coherencia. Una tabla de
    precios mal cargada no rompe la app — cotiza mal, que es peor, porque
    nadie se da cuenta hasta que el cliente reclama.
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

    df = df[COLS_PRECIOS].copy()
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RUTA_PRECIOS, index=False)
    ok = nube.subir_archivo(RUTA_PRECIOS, nube.clave_estado(ARCHIVO_PRECIOS))

    msg_adic = ""
    if adic is not None and not adic.empty:
        adic.columns = [str(c).strip().lower() for c in adic.columns]
        if all(c in adic.columns for c in COLS_ADICIONALES):
            adic["valor"] = pd.to_numeric(adic["valor"], errors="coerce").fillna(0)
            adic[COLS_ADICIONALES].to_parquet(RUTA_ADICIONALES, index=False)
            nube.subir_archivo(RUTA_ADICIONALES,
                               nube.clave_estado(ARCHIVO_ADICIONALES))
            msg_adic = f" y {len(adic)} adicional(es)"
        else:
            msg_adic = " (la hoja 'adicionales' se ignoró: le faltan columnas)"

    guardar_parametros({"ultima_carga": sello_ahora(), "usuario": usuario,
                        "filas": int(len(df))})
    estado_nube = "" if ok else " OJO: no se pudo respaldar en la nube."
    return True, (f"Cargadas {len(df)} combinaciones de precio{msg_adic}."
                  + estado_nube)


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

    # Adicionales: unitarios (se multiplican) o fijos (una sola vez).
    detalle_adic, total_adic = [], 0.0
    tabla_adic = leer_adicionales()
    for concepto in (adicionales or []):
        fila_a = tabla_adic[tabla_adic["concepto"].astype(str) == str(concepto)]
        if fila_a.empty:
            continue
        fila_a = fila_a.iloc[0]
        aplica = str(fila_a.get("aplica_a", "todas")).strip().lower()
        if aplica not in ("todas", "", str(familia).lower()):
            continue
        valor = float(fila_a["valor"])
        monto = valor * int(cantidad) if str(fila_a["tipo"]).lower() == "unitario" else valor
        detalle_adic.append({"concepto": str(concepto), "monto": monto})
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
        "total_adicionales": total_adic,
        "total": total,
        "unitario_con_adicionales": total / int(cantidad) if cantidad else 0.0,
        "minimo": minimo,
        "dias_entrega": int(pd.to_numeric(fila.get("dias_entrega"),
                                          errors="coerce") or 0),
        "incluye": str(fila.get("incluye", "")),
        "escala_desde": int(fila["desde_cantidad"]),
    }


def texto_solicitud(resultado: dict, seleccion: dict, datos_cliente: dict) -> str:
    """
    Arma el mensaje que el cliente le manda a comercial. Lleva TODO lo
    necesario para atenderlo sin volver a preguntar: qué quiere, cuánto,
    para quién y el valor estimado si se pudo calcular.
    """
    lineas = ["Solicitud de cotización · Sociedad Bíblica Colombiana", ""]
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
