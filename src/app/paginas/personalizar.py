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
from nucleo.util import esc_md

ss = st.session_state
params = cotizador.leer_parametros()
simulada = cotizador.es_simulada()

tope("Personalizar", "Armá tu pedido y pedí la cotización")

# Mientras la lista activa sea la de prueba, se dice antes que nada. El
# que pruebe tiene que saber qué está mirando; el que llegue por error,
# también.
if simulada:
    st.warning("**Precios de prueba.** Esta lista es simulada para probar el "
               "cotizador: no es la lista oficial de la SBC y no sirve para "
               "cotizar.")

# ── Qué se va a producir ─────────────────────────────────────────────
# ESTADO: cada selector es la fuente de verdad de su valor. Al cambiar de
# familia se limpian los que dependen de ella (versión, tamaño, cubierta,
# agregados): las opciones de un Tratado no son las de una Biblia, y un
# valor viejo que ya no existe no puede quedar elegido por debajo.
K_FAM, K_CANT, K_ADIC = "_cot_familia", "_cot_cantidad", "_cot_adic"
CAMPOS = (("version", "Versión"), ("tamano", "Tamaño"), ("cubierta", "Cubierta"))

# Siempre las cinco familias; la lista de precios puede agregar otras. Las
# que no tienen precio se cotizan a pedido (p. ej. "Producto propio").
familias = list(FAMILIAS) + [f for f in cotizador.opciones("familia")
                             if f not in FAMILIAS]
if ss.get(K_FAM) not in familias:
    ss[K_FAM] = familias[0]
if K_CANT not in ss:
    ss[K_CANT] = cotizador.minimo_de(ss[K_FAM]) or 800


def _al_cambiar_familia() -> None:
    for campo, _ in CAMPOS:
        ss.pop(f"_cot_{campo}", None)
    ss[K_ADIC] = []
    minimo = cotizador.minimo_de(ss[K_FAM])
    if minimo:
        ss[K_CANT] = minimo           # arrancar en lo mínimo que se produce


def _usar_cantidad(n: int) -> None:
    ss[K_CANT] = int(n)


familia = st.selectbox("¿Qué querés personalizar?", familias, key=K_FAM,
                       on_change=_al_cambiar_familia)

seleccion: dict = {}
for campo, etiqueta in CAMPOS:
    valores = cotizador.opciones(campo, {"familia": familia, **seleccion})
    clave = f"_cot_{campo}"
    if not valores:
        ss.pop(clave, None)
        continue
    if ss.get(clave) not in valores:
        ss[clave] = valores[0]
    seleccion[campo] = st.selectbox(etiqueta, valores, key=clave)

# Solo se ofrecen los agregados que aplican a esta familia.
ofrecidos = cotizador.adicionales_para(familia)
elegidos: list = []
if ofrecidos:
    ss[K_ADIC] = [a for a in ss.get(K_ADIC, []) if a in ofrecidos]
    elegidos = st.multiselect("Agregados", ofrecidos, key=K_ADIC,
                              placeholder="Elegí uno o varios (opcional)",
                              help="Por ejemplo, la hoja de inserto.")

cantidad = st.number_input("Cantidad", min_value=1, step=100, key=K_CANT)

# ── Cálculo ──────────────────────────────────────────────────────────
resultado = cotizador.cotizar(familia, int(cantidad), seleccion, elegidos)

if resultado.get("ok"):
    st.markdown(f"## {fmt_pesos(resultado['total'])}")
    st.caption(f"{fmt_pesos(resultado['unitario_con_adicionales'])} por unidad "
               f"· {int(resultado['cantidad']):,} unidades".replace(",", ".")
               + (" · PRECIO DE PRUEBA" if simulada else ""))
    detalle = [f"Producto: {resultado['referencia'] or familia}",
               f"Precio por unidad: {fmt_pesos(resultado['unitario'])} "
               f"(escala desde {resultado['escala_desde']:,} unidades)".replace(",", "."),
               f"Subtotal: {fmt_pesos(resultado['subtotal'])}"]
    for a in resultado["adicionales"]:
        detalle.append(f"{a['concepto']} ({a['tipo']}): {fmt_pesos(a['monto'])}")
    if resultado["dias_entrega"]:
        detalle.append(f"Entrega estimada: {resultado['dias_entrega']} días")
    if resultado["incluye"]:
        detalle.append(f"Incluye: {resultado['incluye']}")
    with st.expander("Ver el detalle"):
        for linea in detalle:
            st.markdown(f"- {esc_md(linea)}")
    if resultado.get("no_aplican"):
        st.warning("No se sumó (no aplica a este producto): "
                   + ", ".join(resultado["no_aplican"]))
    st.caption("Valor estimado, sujeto a confirmación comercial.")
else:
    st.info(resultado["mensaje"])
    if resultado.get("motivo") == "bajo_minimo":
        st.button(f"Cotizar el mínimo: {resultado['minimo']:,} unidades".replace(",", "."),
                  key="_cot_usar_minimo", on_click=_usar_cantidad,
                  args=(resultado["minimo"],), use_container_width=True)

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
                                    datos, simulada=simulada)

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
               "de contacto en Configuración.")

st.download_button("Descargar la solicitud", mensaje.encode("utf-8"),
                   file_name="solicitud_cotizacion_sbc.txt",
                   mime="text/plain", use_container_width=True,
                   key="_cot_descargar")

with st.expander("Ver lo que se envía"):
    st.text(mensaje)
