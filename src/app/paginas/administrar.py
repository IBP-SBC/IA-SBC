"""
paginas/administrar.py
======================
Todo lo que hay que parametrizar, detrás de la clave.

Está en UNA pantalla con pestañas y no en cuatro secciones del menú
porque el menú de abajo es del visitante: si se llena de opciones que
solo sirven para configurar, la app deja de sentirse una app y vuelve a
ser un tablero.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from app.estado import encabezado_carga, salir, solo_admin, usuario_actual
from app.ui import metricas, tope
from nucleo import biblia, cotizador, indice, nube
from nucleo.config import EXTENSIONES_SOPORTADAS, TAM_MAX_MB
from nucleo.indice import AMBITO_INTERNO, AMBITO_PUBLICO
from nucleo.instrucciones import (
    guardar_instrucciones,
    leer_instrucciones,
    restaurar_por_defecto,
)
from nucleo.modelo import (
    REGLAS_FIJAS,
    estado as estado_modelo,
    guardar_modelo_activo,
    listar_modelos,
    modelos_para_conversar,
    probar_modelo,
)
from nucleo.util import sello_legible, tam_legible

tope("Administrar", "Configuración de la app")
solo_admin()

st.caption(f"Sesión de {usuario_actual()}")
if st.button("Cerrar sesión", key="_adm_salir"):
    salir()
    st.rerun()

t_docs, t_texto, t_precios, t_instr, t_mant = st.tabs(
    ["Documentos", "Texto bíblico", "Precios", "Instrucciones", "Modelo"])


# ════════════════════════════════════════════════════════════════════
# DOCUMENTOS
# ════════════════════════════════════════════════════════════════════
with t_docs:
    estado = indice.resumen_estado()
    encabezado_carga(
        titulo="Cargar o actualizar documentos",
        estado="",
        resumen=(f"**{estado['publicos']} públicos** y "
                 f"**{estado['internos']} internos** en "
                 f"{estado['fragmentos']:,} fragmentos".replace(",", ".")
                 if estado["documentos"] else "**Sin documentos todavía.**"),
        ultima=estado["ultima_carga"],
        ayuda=(
            "- **El ámbito es lo más importante de esta pantalla.** Público = "
            "lo puede consultar cualquiera que abra la app sin clave. Interno "
            "= planes, presupuestos y estrategia, solo para vos.\n"
            "- Si subís un archivo con un nombre que ya existe, **se "
            "actualiza**: la versión nueva reemplaza a la anterior.\n"
            "- Formatos: "
            + ", ".join(sorted(e.lstrip('.') for e in EXTENSIONES_SOPORTADAS))
            + f". Máximo {TAM_MAX_MB} MB.\n"
            "- Los PDF escaneados no dejan texto: hay que pasarles OCR antes."),
    )

    ambito = st.radio(
        "Ámbito de lo que voy a subir",
        [AMBITO_PUBLICO, AMBITO_INTERNO],
        format_func=lambda a: ("Público · lo ve cualquiera"
                               if a == AMBITO_PUBLICO else
                               "Interno · solo con clave"),
        key="_adm_ambito", horizontal=True, index=1)

    archivos = st.file_uploader(
        "Archivos", type=[e.lstrip(".") for e in sorted(EXTENSIONES_SOPORTADAS)],
        accept_multiple_files=True, key="_adm_uploader")
    nota = st.text_input("Nota (opcional)", key="_adm_nota")

    if archivos and st.button("Procesar e indexar", type="primary",
                              key="_adm_procesar"):
        barra = st.progress(0.0, text="Procesando…")
        for i, arch in enumerate(archivos, start=1):
            datos = arch.getvalue()
            if len(datos) > TAM_MAX_MB * 1024 * 1024:
                st.error(f"**{arch.name}** pesa {tam_legible(len(datos))}; "
                         f"el máximo es {TAM_MAX_MB} MB.")
            else:
                r = indice.indexar_documento(arch.name, datos, usuario_actual(),
                                             nota, ambito)
                if r.get("ok"):
                    st.success(f"**{r['documento']}** · {r['mensaje']} "
                               f"{r['fragmentos']} fragmentos.")
                    if r.get("aviso"):
                        st.warning(f"↳ {r['aviso']}")
                else:
                    st.error(f"**{r['documento']}** · {r['mensaje']}")
            barra.progress(i / len(archivos))
        barra.empty()
        st.cache_resource.clear()

    registro = indice.leer_registro()
    if registro:
        st.markdown("##### Lo que hay cargado")
        filas = [{
            "Documento": n,
            "Ámbito": ("Público" if m.get("ambito", AMBITO_INTERNO) == AMBITO_PUBLICO
                       else "Interno"),
            "Fragmentos": int(m.get("fragmentos", 0)),
            "Actualizado": sello_legible(m.get("fecha")),
            "Nube": "sí" if m.get("en_nube") else "no",
        } for n, m in sorted(registro.items())]
        df = pd.DataFrame(filas)
        st.dataframe(df, hide_index=True, use_container_width=True,
                     height=min(38 + 35 * len(df), 420))

        c1, c2 = st.columns([3, 1])
        objetivo = c1.selectbox("Eliminar", sorted(registro), key="_adm_borrar")
        if c2.checkbox("Confirmo", key="_adm_borrar_ok") and st.button(
                "Eliminar definitivamente", key="_adm_borrar_btn"):
            st.warning(indice.eliminar_documento(objetivo))
            st.cache_resource.clear()
            st.rerun()


# ════════════════════════════════════════════════════════════════════
# TEXTO BÍBLICO
# ════════════════════════════════════════════════════════════════════
with t_texto:
    res = biblia.resumen()
    encabezado_carga(
        titulo="Texto bíblico",
        estado="",
        resumen=(f"**{res['versiculos']:,} versículos** de {res['libros']} "
                 f"libros en {res['versiones']} versión(es)".replace(",", ".")
                 if res["versiculos"] else "**Sin texto cargado todavía.**"),
        ultima=None,
        ayuda=(
            "- El texto se carga **ya estructurado**, con una fila por "
            "versículo y estas columnas exactas: `version`, `libro`, `orden`, "
            "`capitulo`, `versiculo`, `texto`.\n"
            "- `orden` es el número del libro (1 = Génesis) y sirve para que "
            "la lista no salga en orden alfabético.\n"
            "- **La extracción desde los PDF no se hace acá.** Se hace una "
            "vez, se revisa contra el impreso y recién entonces se sube: un "
            "error de extracción no es un bug, es un texto bíblico mal "
            "citado.\n"
            "- No se guarda un corpus con versículos vacíos: se avisa cuántos "
            "y no se escribe nada."),
    )
    if res["detalle"]:
        st.dataframe(pd.DataFrame(res["detalle"]), hide_index=True,
                     use_container_width=True)

    archivo_biblia = st.file_uploader("Corpus (.csv o .parquet)",
                                      type=["csv", "parquet"],
                                      key="_adm_biblia_file")
    if archivo_biblia and st.button("Cargar texto", type="primary",
                                    key="_adm_biblia_btn"):
        try:
            datos = archivo_biblia.getvalue()
            if archivo_biblia.name.lower().endswith(".parquet"):
                df_b = pd.read_parquet(io.BytesIO(datos))
            else:
                df_b = pd.read_csv(io.BytesIO(datos), sep=None, engine="python")
            df_b.columns = [str(c).strip().lower() for c in df_b.columns]
            ok, msg = biblia.guardar_corpus(df_b)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")


# ════════════════════════════════════════════════════════════════════
# PRECIOS Y CONTACTO
# ════════════════════════════════════════════════════════════════════
with t_precios:
    params = cotizador.leer_parametros()
    precios = cotizador.leer_precios()
    encabezado_carga(
        titulo="Lista de precios",
        estado="",
        resumen=(f"**{len(precios)} combinaciones** cargadas"
                 if not precios.empty else
                 "**Sin lista de precios.** El cotizador funciona igual, pero "
                 "sin calcular el valor: envía la solicitud a comercial."),
        ultima=params.get("ultima_carga"),
        ayuda=(
            "- Una fila por combinación cotizable. Las escalas por volumen se "
            "resuelven con `desde_cantidad`: se aplica el precio de la fila "
            "con el mayor `desde_cantidad` que no supere lo pedido.\n"
            "- `minimo` es el mínimo de producción de esa familia. El "
            "cotizador lo muestra ANTES de que el cliente arme todo el "
            "pedido.\n"
            "- En Excel podés agregar una segunda hoja llamada `adicionales` "
            "con las columnas `concepto`, `tipo` (unitario o fijo), `valor` y "
            "`aplica_a`.\n"
            "- Los precios se validan al cargar: si hay celdas vacías, texto "
            "donde va un número o precios en cero, **no se guarda nada**."),
    )
    st.download_button("Descargar la plantilla", cotizador.plantilla_csv(),
                       file_name="plantilla_precios_sbc.csv", mime="text/csv",
                       key="_adm_plantilla")

    archivo_precios = st.file_uploader("Lista de precios (.xlsx o .csv)",
                                       type=["xlsx", "xlsm", "csv"],
                                       key="_adm_precios_file")
    if archivo_precios and st.button("Cargar precios", type="primary",
                                     key="_adm_precios_btn"):
        ok, msg = cotizador.cargar_tabla(archivo_precios.getvalue(),
                                         archivo_precios.name, usuario_actual())
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()

    if not precios.empty:
        st.dataframe(precios, hide_index=True, use_container_width=True,
                     height=min(38 + 35 * len(precios), 360))

    st.markdown("##### A dónde llegan las solicitudes")
    numero = st.text_input(
        "WhatsApp de contacto", value=str(params.get("whatsapp", "")),
        key="_adm_whatsapp",
        help="Con indicativo y sin signos ni espacios. Ejemplo: 573164903235")
    if st.button("Guardar contacto", key="_adm_contacto_btn"):
        limpio = "".join(c for c in numero if c.isdigit())
        cotizador.guardar_parametros({"whatsapp": limpio})
        st.success("Contacto guardado." if limpio else
                   "Se quitó el número: el botón de WhatsApp queda oculto.")


# ════════════════════════════════════════════════════════════════════
# INSTRUCCIONES
# ════════════════════════════════════════════════════════════════════
with t_instr:
    st.markdown("Esto es lo primero que lee el asistente en cada "
                "conversación: quién es, cómo responde y qué no puede hacer.")
    texto = st.text_area("Instrucciones", value=leer_instrucciones(),
                         height=380, key="_adm_main",
                         label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("Guardar", type="primary", key="_adm_main_guardar",
                 use_container_width=True):
        msg = guardar_instrucciones(texto, usuario_actual())
        (st.error if msg.startswith("No se") or "FALLÓ" in msg
         else st.success)(msg)
    if c2.button("Restaurar", key="_adm_main_restaurar",
                 use_container_width=True):
        st.info(restaurar_por_defecto(usuario_actual()))
        st.rerun()
    with st.expander("Reglas que van siempre (no se editan)"):
        st.code(REGLAS_FIJAS, language="text")


# ════════════════════════════════════════════════════════════════════
# MODELO Y MANTENIMIENTO
# ════════════════════════════════════════════════════════════════════
with t_mant:
    ok_nube, msg_nube = nube.probar_conexion()
    (st.success if ok_nube else st.error)(f"Supabase: {msg_nube}")
    ok_modelo, msg_modelo = estado_modelo()
    (st.success if ok_modelo else st.warning)(f"Modelo: {msg_modelo}")

    st.markdown("El listado del proveedor no garantiza que un modelo sirva "
                "para conversar: los de imagen, audio o embeddings no "
                "responden. La única prueba es preguntarle.")
    if st.button("Consultar modelos del proveedor", key="_adm_modelos"):
        nombres, detalle = listar_modelos()
        st.session_state["_modelos_listados"] = nombres
        st.caption(detalle)

    listados = st.session_state.get("_modelos_listados", [])
    if listados:
        candidatos = modelos_para_conversar(listados)
        c1, c2 = st.columns([3, 1])
        elegido = c1.selectbox(f"Sirven para conversar ({len(candidatos)} de "
                               f"{len(listados)})", candidatos, key="_adm_modelo_sel")
        if c2.button("Probar", key="_adm_probar"):
            ok_p, detalle_p = probar_modelo(elegido)
            (st.success if ok_p else st.error)(detalle_p)
        if st.button(f"Usar '{elegido}' de ahora en adelante",
                     key="_adm_activar"):
            st.info(guardar_modelo_activo(elegido, usuario_actual()))
            st.rerun()

    st.divider()
    estado = indice.resumen_estado()
    metricas([("Documentos", str(estado["documentos"])),
              ("Fragmentos", f"{estado['fragmentos']:,}".replace(",", ".")),
              ("Versículos", f"{biblia.resumen()['versiculos']:,}".replace(",", "."))])
    if st.button("Reconstruir el índice", key="_adm_reindexar"):
        with st.spinner("Reindexando…"):
            resultados = indice.reconstruir_indice(usuario_actual())
        buenos = sum(1 for r in resultados if r.get("ok"))
        st.success(f"Reindexados {buenos} de {len(resultados)}.")
        st.cache_resource.clear()
