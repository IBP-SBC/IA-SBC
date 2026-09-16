# IA-SBC · Asistente de decisiones de la Sociedad Bíblica Colombiana

Chat que responde preguntas del día a día **con base en los documentos
oficiales de la SBC** y siempre dice de dónde sacó cada cosa.

- **Producción:** https://iasbc.streamlit.app
- **Repositorio:** `IA-SBC`
- **Almacenamiento:** Supabase Storage, bucket `ia-sbc` (propio de esta
  app: NO comparte bucket con `sbc_ventas` ni con `sbc_demanda`)

---

## El porqué

El conocimiento de la SBC ya existe: planes, informes de gestión,
estudios Patmos, estrategias. El problema es que está en decenas de
documentos que nadie alcanza a leer cuando tiene que decidir algo hoy.

Esta app no reemplaza el criterio de nadie. Pone a la mano, en segundos,
lo que ya decidimos y lo que ya aprendimos, **con la fuente al lado**
para que quien decide pueda verificarlo.

---

## Cómo funciona (en tres frases)

1. Un admin sube documentos. La app extrae el texto, lo parte en
   fragmentos y arma un índice de búsqueda.
2. Cuando alguien pregunta, la app busca los fragmentos más relevantes y
   se los pasa al modelo junto con `main.md` (las instrucciones
   generales).
3. El modelo responde citando los fragmentos. La pantalla muestra abajo
   qué fuentes se usaron.

**Si un documento no está cargado, la app no lo sabe.** Es a propósito.

---

## Estructura

```
IA-SBC/
├── main.md                  ← instrucciones generales (editables en la app)
├── requirements.txt
├── validar_ast.py           ← valida el código (NameError, keys duplicadas)
├── auditoria_iasbc.py       ← 39 checks de que los datos signifiquen lo correcto
├── prueba_arranque.py       ← AppTest: cada página abre sin trunar
├── .streamlit/config.toml   ← sin [theme] (forzaría el modo claro)
├── data/                    ← VACÍO en el repo; los datos viven en Supabase
└── src/
    ├── app/                 ← dibuja (Home.py + estado.py + paginas/)
    └── nucleo/              ← calcula (config, util, nube, extraccion,
                                indice, instrucciones, claude)
```

La regla que ordena todo: **`app/` no calcula, `nucleo/` no dibuja.**

---

## Antes de subir un cambio

```
python3 validar_ast.py && python3 auditoria_iasbc.py && python3 prueba_arranque.py
```

Si algo falla, no se sube. Si un arreglo revela una regla que puede
volver a romperse, se agrega un check a `auditoria_iasbc.py`.

---

## Decisiones técnicas y por qué

| Decisión | Por qué |
|---|---|
| Búsqueda **BM25 léxica**, no embeddings | Sin segunda cuenta ni costo por documento; es explicable y funciona muy bien con vocabulario propio ("S5", "encuadernación", un ISBN). Los embeddings son el paso 2, no el 1. |
| API por **requests + SSE**, no el SDK | El SDK de Anthropic pasó a 1.0 en agosto de 2026 con cambios que rompen. Ya hablamos con Supabase por REST: una dependencia menos y el código a la vista. |
| **Proveedor configurable** (`anthropic` / `google` / compatible OpenAI) | La app tiene que poder salir hoy con la cuenta que haya hoy, y cambiar después sin tocar código. Google se atiende por su base compatible con OpenAI, así que hay un solo cliente para todos menos Claude. |
| **Modo búsqueda** cuando no hay llave | Sin modelo no se redacta: se muestran los pasajes con su fuente. Menos cómodo y honesto; además sirve como buscador desde el primer día. |
| **No se envía `temperature`** | En los modelos 5, cualquier valor distinto del defecto devuelve error 400. |
| El **nombre del archivo es la identidad** del documento | Subir otra vez `Informe 2025.pdf` lo actualiza. `Informe 2025 v2.pdf` es otro documento: no se adivinan identidades parecidas. |
| **Guarda anti-pisado** del registro | El disco de Streamlit Cloud es efímero. En `sbc_ventas` ese patrón borró histórico tres veces. |
| Extensión ≠ contenido se **rechaza**, no se adivina | Un `.pdf` que por dentro es un Word se lee mal y nadie sabría por qué. Mejor decir qué es y cómo renombrarlo. |

---

## Versiones

- **1.1.0** — el proveedor del modelo se elige en los Secrets
  (`anthropic`, `google` o cualquiera compatible con OpenAI) y, si no hay
  ninguno, la app funciona en **modo búsqueda**: muestra los pasajes
  encontrados con su fuente en vez de inventar una respuesta. Se agregó
  el listado de modelos reales del proveedor y el cuaderno de Colab.
- **1.0.0** — primera versión. Chat con fuentes, carga y actualización de
  documentos por nombre, editor de `main.md`, roles admin/colaborador,
  persistencia en Supabase.
