"""
paginas/personalizar.py
=======================
Armar un pedido personalizado y pedir la cotización.

TRES COSAS QUE ESTA PANTALLA HACE SIEMPRE, aunque incomoden:
1. **Dice el mínimo de producción antes de que el cliente se ilusione.**
   Una Biblia con el logo de la iglesia se fabrica montando una corrida
   completa en la planta. Enterarse al final es peor que saberlo al
   principio.
2. **No inventa precios.** Si la lista no está cargada, se puede enviar
   la solicitud igual y comercial responde. Un "precio de referencia"
   sacado de la nada termina en un reclamo.
3. **Dice el tiempo de entrega real**, que no es el de un producto de
   catálogo.
"""
from __future__ import annotations

import urllib.parse

import streamlit as st

from app.ui import tope
from nucleo import cotizador
from nucleo.cotizador import FAMILIAS, fmt_pesos

tope("Personalizar", "Armá tu pedido y pedí la cotización")

params = cotizador.leer_parametros()
hay_precios = cotizador.hay_precios()

# ── Qué se va a producir ─────────────────────────────────────────────
familias_disponibles = cotizador.opciones("familia") or FAMILIAS
familia = st.selectbox("¿Qué querés personalizar?", familias_disponibles,
                       key="_cot_familia")

seleccion: dict = {}
for campo, etiqueta in (("version", "Versión"), ("tamano", "Tamaño"),
                        ("cubierta", "Cubierta")):
    valores = cotizador.opciones(campo, {"familia": familia, **seleccion})
    if valores:
        seleccion[campo] = st.selectbox(etiqueta, valores, key=f"_cot_{campo}")

adicionales_tabla = cotizador.leer_adicionales()
elegidos = []
if not adicionales_tabla.empty:
    conceptos = [str(c) for c in adicionales_tabla["concepto"].dropna().unique()]
    elegidos = st.multiselect("Agregados", conceptos, key="_cot_adic",
                              help="Logo, grabado del nombre, hoja de inserto.")

cantidad = st.number_input("Cantidad", min_value=1, value=800, step=100,
                           key="_cot_cantidad")

# ── Cálculo ──────────────────────────────────────────────────────────
resultado = cotizador.cotizar(familia, int(cantidad), seleccion, elegidos)

if resultado.get("ok"):
    st.markdown(f"## {fmt_pesos(resultado['total'])}")
    st.caption(f"{fmt_pesos(resultado['unitario_con_adicionales'])} por unidad "
               f"· {int(resultado['cantidad']):,} unidades".replace(",", "."))
    detalle = [f"Producto: {resultado['referencia'] or familia}"]
    if resultado["adicionales"]:
        for a in resultado["adicionales"]:
            detalle.append(f"{a['concepto']}: {fmt_pesos(a['monto'])}")
    if resultado["dias_entrega"]:
        detalle.append(f"Entrega estimada: {resultado['dias_entrega']} días")
    if resultado["incluye"]:
        detalle.append(f"Incluye: {resultado['incluye']}")
    with st.expander("Ver el detalle"):
        for linea in detalle:
            st.markdown(f"- {linea}")
    st.caption("Valor estimado, sujeto a confirmación comercial.")
else:
    st.info(resultado["mensaje"])

# ── Datos de contacto y envío ────────────────────────────────────────
st.markdown("#### Para responderte")
iglesia = st.text_input("Iglesia u organización", key="_cot_iglesia")
nombre = st.text_input("Tu nombre", key="_cot_nombre")
telefono = st.text_input("Teléfono", key="_cot_tel")
ciudad = st.text_input("Ciudad", key="_cot_ciudad")
notas = st.text_area("Algo más que debamos saber", key="_cot_notas", height=80)

datos = {"iglesia": iglesia, "nombre": nombre, "telefono": telefono,
         "ciudad": ciudad, "notas": notas, "cantidad": int(cantidad)}
mensaje = cotizador.texto_solicitud(resultado, {"familia": familia, **seleccion},
                                    datos)

faltan = [e for e, v in (("tu nombre", nombre), ("el teléfono", telefono))
          if not str(v).strip()]
if faltan:
    st.caption("Falta " + " y ".join(faltan) + " para poder responderte.")

whatsapp = str(params.get("whatsapp", "")).strip()
if whatsapp and not faltan:
    enlace = ("https://wa.me/" + whatsapp + "?text="
              + urllib.parse.quote(mensaje))
    st.link_button("Enviar por WhatsApp", enlace, use_container_width=True,
                   type="primary")
elif not whatsapp:
    st.caption("El envío por WhatsApp se activa cuando se configure el número "
               "de contacto en Administrar.")

st.download_button("Descargar la solicitud", mensaje.encode("utf-8"),
                   file_name="solicitud_cotizacion_sbc.txt",
                   mime="text/plain", use_container_width=True,
                   key="_cot_descargar")

with st.expander("Ver lo que se envía"):
    st.text(mensaje)
