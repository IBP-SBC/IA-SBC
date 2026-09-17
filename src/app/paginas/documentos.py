"""
paginas/documentos.py
=====================
La biblioteca del asistente. Solo admin.

REGLA CENTRAL: el NOMBRE DEL ARCHIVO es la identidad del documento.
Subir otra vez "Informe 2025.pdf" ACTUALIZA ese documento: se borran sus
fragmentos viejos y se reindexa el contenido nuevo. No quedan dos
versiones conviviendo, que era justo el riesgo (el asistente citando una
cifra derogada con cara de oficial).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.estado import encabezado_carga, es_admin, usuario_actual
from app.ui import encabezado, metricas
from nucleo import indice, nube
from nucleo.config import EXTENSIONES_SOPORTADAS, TAM_MAX_MB
from nucleo.modelo import (
    estado as estado_modelo,
    guardar_modelo_activo,
    listar_modelos,
    modelos_para_conversar,
    probar_modelo,
)
from nucleo.util import sello_legible, tam_legible

if not es_admin():
    st.warning("Esta sección es solo para administradores.")
    st.stop()

encabezado("Documentos",
           "Lo que subas acá es TODO lo que el asistente sabe. Ni más, ni menos.",
           "📚")

estado = indice.resumen_estado()
encabezado_carga(
    titulo="📥 Cargar o actualizar documentos",
    estado="🟢" if estado["documentos"] else "⚪",
    resumen=(f"**{estado['documentos']} documentos** indexados en "
             f"**{estado['fragmentos']:,} fragmentos**".replace(",", ".")
             if estado["documentos"] else "**Sin documentos todavía.**"),
    ultima=estado["ultima_carga"],
    ayuda=(
        "- Formatos que sé leer: "
        + ", ".join(sorted(e.lstrip('.') for e in EXTENSIONES_SOPORTADAS))
        + f". Máximo {TAM_MAX_MB} MB por archivo.\n"
        "- **Si subís un archivo con un nombre que ya existe, se actualiza**: "
        "la versión nueva reemplaza a la anterior por completo.\n"
        "- Si querés conservar las dos versiones, cambiá el nombre "
        "(por ejemplo `Plan 2026 v2.pdf`). Para mí son dos documentos "
        "distintos: no adivino que uno reemplaza al otro.\n"
        "- Los PDF escaneados (fotos de páginas) no dejan texto: hay que "
        "pasarles OCR antes de subirlos. Te aviso cuando pase.\n"
        "- Todo queda respaldado en Supabase, así sobrevive a los reinicios."
    ),
)

archivos = st.file_uploader(
    "Arrastrá uno o varios archivos",
    type=[e.lstrip(".") for e in sorted(EXTENSIONES_SOPORTADAS)],
    accept_multiple_files=True,
    key="_doc_uploader",
)
nota = st.text_input(
    "Nota (opcional)", key="_doc_nota",
    placeholder="Ej.: versión aprobada por junta en agosto",
    help="Se guarda junto al documento para saber qué es cada cosa.",
)

if archivos and st.button("⚙️ Procesar e indexar", type="primary",
                          key="_doc_procesar"):
    barra = st.progress(0.0, text="Procesando…")
    resultados = []
    for i, arch in enumerate(archivos, start=1):
        datos = arch.getvalue()
        if len(datos) > TAM_MAX_MB * 1024 * 1024:
            resultados.append({
                "ok": False, "documento": arch.name,
                "mensaje": f"Pesa {tam_legible(len(datos))}; el máximo es "
                           f"{TAM_MAX_MB} MB.",
            })
        else:
            resultados.append(
                indice.indexar_documento(arch.name, datos, usuario_actual(), nota))
        barra.progress(i / len(archivos), text=f"Procesando… ({i}/{len(archivos)})")
    barra.empty()

    for r in resultados:
        if r.get("ok"):
            detalle = (f"{r['fragmentos']} fragmentos"
                       + (f" (antes tenía {r['fragmentos_previos']})"
                          if r.get("actualizado") else ""))
            st.success(f"**{r['documento']}** · {r['mensaje']} {detalle}")
            if r.get("aviso"):
                st.warning(f"↳ {r['documento']}: {r['aviso']}")
            if r.get("nube", "").startswith(("No se", "BLOQUEADO", "Falló")):
                st.error(f"↳ Nube: {r['nube']}")
        else:
            st.error(f"**{r['documento']}** · {r['mensaje']}")
    st.cache_resource.clear()   # el índice BM25 cambió: hay que recalcularlo

st.divider()

# Tres cifras, no más: cuánto sabe, de cuántas piezas y desde cuándo.
metricas([
    ("Documentos", f"{estado['documentos']}"),
    ("Fragmentos", f"{estado['fragmentos']:,}".replace(",", ".")),
    ("Caracteres indexados", f"{estado['caracteres']:,}".replace(",", ".")),
])

# ── Inventario ───────────────────────────────────────────────────────
st.markdown("### 🗂️ Lo que hay cargado")
registro = indice.leer_registro()

if not registro:
    st.info("Sin documentos. Subí el primero arriba.")
else:
    filas = []
    for nombre, meta in sorted(registro.items()):
        filas.append({
            "Documento": nombre,
            "Fragmentos": int(meta.get("fragmentos", 0)),
            "Páginas/Hojas": int(meta.get("paginas", 0)),
            "Tamaño": tam_legible(meta.get("bytes")),
            "Actualizado": sello_legible(meta.get("fecha")),
            "Por": meta.get("usuario", ""),
            "En nube": "☁️ sí" if meta.get("en_nube") else "⚠️ no",
            "Nota": meta.get("nota", ""),
        })
    df = pd.DataFrame(filas)
    st.dataframe(df, hide_index=True, use_container_width=True,
                 height=min(38 + 35 * len(df), 600))

    avisos = {n: m.get("aviso") for n, m in registro.items() if m.get("aviso")}
    if avisos:
        with st.expander(f"⚠️ Documentos con advertencias ({len(avisos)})"):
            for n, a in avisos.items():
                st.markdown(f"- **{n}**: {a}")

    st.markdown("#### 🗑️ Eliminar un documento")
    c1, c2 = st.columns([3, 1])
    objetivo = c1.selectbox("Documento", sorted(registro), key="_doc_borrar_sel")
    confirmar = c2.checkbox("Confirmo", key="_doc_borrar_chk")
    if st.button("Eliminar definitivamente", key="_doc_borrar_btn",
                 disabled=not confirmar):
        st.warning(indice.eliminar_documento(objetivo))
        st.cache_resource.clear()
        st.rerun()

st.divider()

# ── Mantenimiento ────────────────────────────────────────────────────
with st.expander("🔧 Mantenimiento y diagnóstico"):
    ok, msg = nube.probar_conexion()
    (st.success if ok else st.error)(f"Supabase: {msg}")

    ok_modelo, msg_modelo = estado_modelo()
    (st.success if ok_modelo else st.warning)(f"Modelo: {msg_modelo}")

    st.markdown(
        "**Elegir y probar el modelo.** El listado del proveedor no "
        "garantiza que un modelo atienda conversación: los de imagen, "
        "audio o embeddings no sirven. La única prueba de que funciona es "
        "preguntarle. Lo que elijas acá manda sobre los Secrets y queda "
        "guardado, sin necesidad de volver a desplegar."
    )
    if st.button("🔎 Consultar modelos del proveedor", key="_doc_modelos"):
        nombres, detalle = listar_modelos()
        st.session_state["_modelos_listados"] = nombres
        st.caption(detalle)

    _nombres = st.session_state.get("_modelos_listados", [])
    if _nombres:
        _chat = modelos_para_conversar(_nombres)
        c1, c2 = st.columns([3, 1])
        _elegido = c1.selectbox(
            f"Modelos que sirven para conversar ({len(_chat)} de {len(_nombres)})",
            _chat, key="_doc_modelo_sel")
        if c2.button("Probar", key="_doc_probar_modelo"):
            ok_p, detalle_p = probar_modelo(_elegido)
            (st.success if ok_p else st.error)(detalle_p)
        if st.button(f"✅ Usar '{_elegido}' de ahora en adelante",
                     key="_doc_activar_modelo"):
            st.info(guardar_modelo_activo(_elegido, usuario_actual()))
            st.rerun()
        with st.expander("Ver la lista completa que devolvió el proveedor"):
            st.code("\n".join(_nombres), language="text")

    st.divider()
    st.markdown(
        "**Reconstruir el índice** vuelve a leer todos los originales y "
        "rearma los fragmentos desde cero. Se usa si se cambió el tamaño "
        "de fragmento o si algo quedó raro. No borra documentos."
    )
    if st.button("♻️ Reconstruir el índice", key="_doc_reindexar"):
        with st.spinner("Reindexando todo…"):
            resultados = indice.reconstruir_indice(usuario_actual())
        buenos = sum(1 for r in resultados if r.get("ok"))
        st.success(f"Reindexados {buenos} de {len(resultados)} documentos.")
        for r in resultados:
            if not r.get("ok"):
                st.error(f"{r['documento']}: {r['mensaje']}")
        st.cache_resource.clear()

    if st.button("☁️ Traer todo de la nube otra vez", key="_doc_hidratar"):
        res = nube.hidratar(forzar=True)
        st.info(f"Bajados {res['documentos']} documentos y {res['estado']} "
                "archivos de estado.")
        st.cache_resource.clear()
        st.rerun()
