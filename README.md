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
├── auditoria_iasbc.py       ← 175 checks de que los datos signifiquen lo correcto
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
| El tema define **solo el acento, uno por modo** (`[theme.light]` y `[theme.dark]`), nunca `[theme]` a secas | `[theme]` fuerza el modo claro para todos. Las dos secciones por modo respetan la preferencia del celular y quitan el rojo de fábrica de Streamlit de todos los campos (verificado en un navegador, en claro y en oscuro). |
| **Sin usuario de fábrica** | Abrió dos huecos (v2.2 y v2.3.0) con una clave escrita en un código que es público. Sin Secrets legibles nadie entra, y la pantalla de acceso dice por qué y en qué línea. |
| **Streamlit fijo en 1.57.0** | La piel (CSS) se verificó en un navegador con esa versión. En la 1.66 cambian los selectores del selectbox y de las pestañas que usa la demo Millca: subir de versión exige revisarla primero. |

---

## Versiones

- **2.4.0** — Conversar: después de cada respuesta aparecen **tres preguntas
  sugeridas** para seguir. Salen de los títulos de los documentos que se
  usaron para responder (opción elegida por la SBC): no cuestan nada extra,
  funcionan sin modelo y siempre tienen respuesta en lo cargado. No repiten
  lo que la persona ya preguntó, y solo se muestran bajo la última
  respuesta. Instrucciones (main.md): **postura interconfesional** de la
  SBC, respuestas desde las ciencias bíblicas, citas en RVR1960 solo si el
  texto está en los documentos. Búsqueda: el recorte de plurales que
  escribí en la v1.0 **no unía singular y plural en las palabras
  terminadas en -e** («tatuaje» no encontraba «tatuajes», «cliente» no
  encontraba «clientes»; tampoco «ley» y «leyes», «rey» y «reyes», «mes» y
  «meses»). Ahora caen en la misma raíz; un check con 14 pares lo vigila.
  Troceo: el solape entre fragmentos **ya no se pone delante de un
  título**; en los documentos de preguntas, cada respuesta empezaba con el
  final de la anterior. Para que los documentos ya cargados tomen el
  troceo nuevo: Configuración → Modelo → Reconstruir el índice.

- **2.3.1** — Acceso: la app confundía **Secrets ilegibles** (comillas
  curvas al pegarlos desde el iPad, un bloque repetido) con "no hay
  Secrets": nadie podía entrar, la pantalla solo decía "incorrecto" y el
  usuario de fábrica quedaba habilitado, con su clave escrita en el código
  público. Ahora **no existe usuario de fábrica**; la pantalla de acceso
  dice si los Secrets no se pueden leer y cerca de qué línea, y muestra la
  versión y cuántos administradores leyó. El correo se compara sin tildes
  (el corrector del iPhone escribe "promoción"). Cotizador: la **lista
  simulada rige sola** mientras no haya lista oficial, anunciada como
  prueba (antes había que activarla como administrador). Colab: el commit
  lleva la versión real (todos decían "v1.1.0").

- **2.3.0** — Acceso: el administrador es `director.promocion@sbcol.org`
  (la clave vive solo en los Secrets). Se corrigieron tres huecos: la
  sección de usuarios que documenté en la v2.0 tenía una sintaxis TOML que
  no creaba usuarios; en ese caso la app caía en un usuario de fábrica
  escrito en el código; y no se miraba el rol, así que cualquier usuario
  entraba a la configuración. El botón Entrar pasó arriba a la izquierda.
  Biblia: **Nuevo Testamento Reina-Valera 1909** de ejemplo (27 libros,
  260 capítulos, 7.955 versículos, sin las notas finales de las epístolas)
  mientras no haya texto oficial, con navegación que cruza de libro.
  Los botones Anterior/Siguiente **nunca habían funcionado** (en la SBC ni
  en Millca): el selector pisaba el valor. Y al pasar de capítulo la
  pantalla quedaba abajo, en el final del capítulo nuevo: ahora va a su
  comienzo (verificado en un navegador con Streamlit 1.57 y 1.66). Color:
  el acento del tema se fija **por modo** (`[theme.light]` y
  `[theme.dark]`), así ningún campo se pone rojo al tocarlo y el modo
  oscuro sigue la preferencia del celular; en modo oscuro la pestaña
  activa de la barra se leía con contraste 2,18:1 y ahora 7,47:1.
  Cotizador: **lista de precios
  de prueba** cargable con un botón y anunciada en pantalla; los agregados
  se cruzan por familia (antes podían desaparecer de la cotización sin
  aviso) y se validan al cargar. La nube recuerda por un minuto lo que no
  existe en el bucket, en vez de consultarlo en cada toque.

- **2.2.1** — Demo Millca: la barra inferior **deja libre la esquina del
  distintivo de Streamlit Cloud** (lo pinta la plataforma por fuera de la
  app y tapaba la tercera pestaña en el celular; el `width:100%` que
  Streamlit pone a sus contenedores anulaba el `right`). **Modo claro /
  oscuro** elegible en Mi Altar, con paleta completa para toda la pantalla
  y persistido en la URL (`?tema=oscuro`) para que sobreviva al refresco y
  se pueda compartir. El tamaño de letra pasó de deslizador a tres botones.

- **2.2.0** — **Demo Comunidad Millca** en /millca, /millca-inspiracion
  y /millca-altar: los tres botones de la propuesta con piel propia
  (pastel, serif), el evangelio de Juan completo en Reina-Valera 1909
  (dominio público, 879 versículos verificados), los reels reales de
  Millca y dos videos de YouTube incrustados, y el perfil de la usuaria.
  Se configura desde Configuración → Millca. Dos bugs de la v2.1 que la
  demo sacó a la luz y quedaron corregidos en toda la app: la barra
  inferior era transparente (Streamlit no expone `--background-color`)
  y el botón "Entrar" existía pero la cabecera lo tapaba. `st.iframe`
  reemplaza al `components.iframe` que se retira en 2026.

- **2.1.0** — la barra inferior se apilaba en vertical en el celular
  (Streamlit pone las columnas una debajo de otra en pantallas angostas):
  ahora se le fuerza la fila y el reparto de ancho. Fuera los iconos de
  toda la interfaz: solo texto. La configuración salió de la barra y subió
  a la esquina superior derecha, así abajo quedan las tres secciones que
  la gente usa.

- **2.0.0** — la app se abre a cualquiera. Navegación inferior de tres
  secciones (Conversar · Biblia · Personalizar), sin clave: la clave quedó
  solo para **Administrar**. Los documentos ahora tienen **ámbito**
  (público o interno) y la búsqueda pública no puede alcanzar lo interno,
  ni siquiera pidiéndolo por nombre. Nuevos módulos: `biblia.py` (lectura
  por capítulo) y `cotizador.py` (precios desde una tabla que carga
  comercial, nunca escritos en el código).

- **1.2.0** — dos cosas. (1) Cuando el modelo terminaba sin escribir una
  sola letra, el chat quedaba **mudo** y la respuesta vacía se guardaba en
  el historial, envenenando las preguntas siguientes de esa sesión (por eso
  "reiniciar la app" lo arreglaba). Ahora se reintenta una vez con más
  presupuesto, se explica el motivo real si vuelve a pasar, y los turnos
  vacíos no se guardan ni se envían. Hay un desplegable con el detalle
  técnico de cada respuesta, solo para admin. (2) Trabajo visual:
  encabezados con la franja institucional, burbujas de chat, fuentes como
  etiquetas, preguntas de arranque en botones y tarjetas de cifras en
  Documentos, todo funcionando en modo claro y oscuro.

- **1.1.2** — las tildes y las eñes de la respuesta llegaban rotas
  ("Activo-PÃºblico"): requests asume ISO-8859-1 cuando el servidor manda
  `text/*` sin declarar el juego de caracteres. Ahora el stream se
  decodifica como UTF-8 explícitamente, que es lo que define el protocolo
  SSE. Tres checks nuevos lo vigilan.

- **1.1.1** — los errores del proveedor muestran **lo que el proveedor
  dijo** (antes un 404 se traducía a "no reconoce ese modelo" aunque el
  modelo estuviera en la lista, y el detalle real se descartaba). Se
  agregó elegir, **probar** y activar el modelo desde Mantenimiento, con
  la elección guardada en la nube: corregir el modelo ya no exige
  redesplegar ni tocar los Secrets.

- **1.1.0** — el proveedor del modelo se elige en los Secrets
  (`anthropic`, `google` o cualquiera compatible con OpenAI) y, si no hay
  ninguno, la app funciona en **modo búsqueda**: muestra los pasajes
  encontrados con su fuente en vez de inventar una respuesta. Se agregó
  el listado de modelos reales del proveedor y el cuaderno de Colab.
- **1.0.0** — primera versión. Chat con fuentes, carga y actualización de
  documentos por nombre, editor de `main.md`, roles admin/colaborador,
  persistencia en Supabase.
