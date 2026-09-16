"""
nucleo/config.py
================
PARÁMETROS CENTRALIZADOS de IA-SBC. Fuente única de verdad: si algo se
usa en más de un módulo, se declara acá y se IMPORTA. Nada de textos
sueltos repetidos (esa fue la lección de los nombres de materias primas
en sbc_ventas: 49 apariciones sueltas permitieron escribir una variante
mal y romper el cruce).

POR QUÉ existe esta app (círculo dorado):
  PORQUÉ  Las decisiones del día a día en la SBC se toman sin tener a la
          mano lo que YA está escrito y estudiado (Patmos, planes,
          informes, estrategias). El conocimiento existe, pero está en
          PDFs que nadie alcanza a leer.
  CÓMO    Un asistente que SOLO responde con base en los documentos
          oficiales de la SBC, citando de dónde salió cada cosa.
  QUÉ     Un chat en la nube, alimentado por archivos que el equipo sube,
          con un archivo main.md que define cómo debe conversar.
"""
from __future__ import annotations

from pathlib import Path

# ── Identidad ────────────────────────────────────────────────────────
APP_NOMBRE = "IA · SBC"
APP_SUBTITULO = "Asistente de decisiones de la Sociedad Bíblica Colombiana"
APP_VERSION = "1.1.2"

# ── Rutas locales ────────────────────────────────────────────────────
# parents[2] = raíz del repo (src/nucleo/config.py → src/ → raíz)
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "documentos"     # originales tal como se subieron
ESTADO_DIR = DATA_DIR / "estado"       # índice, registro, sellos

RUTA_REGISTRO = ESTADO_DIR / "registro.json"      # qué documentos hay
RUTA_CHUNKS = ESTADO_DIR / "fragmentos.parquet"   # el índice de búsqueda
RUTA_MAIN = ROOT / "main.md"                      # instrucciones generales
RUTA_MAIN_LOCAL = ESTADO_DIR / "main.md"          # versión editada en la app

# ── Nube (Supabase Storage) ──────────────────────────────────────────
# El bucket es PROPIO de esta app: NO se comparte con sbc_ventas ni con
# sbc_demanda. Un error en una app no puede tocar los datos de la otra.
BUCKET_DEFECTO = "ia-sbc"
PREFIJO_DOCS = "documentos"     # bucket/documentos/<archivo>
PREFIJO_ESTADO = "estado"       # bucket/estado/registro.json, fragmentos.parquet, main.md
TIMEOUT_NUBE = 60               # segundos; los PDF grandes tardan

# ── Modelo de lenguaje ───────────────────────────────────────────────
# El proveedor NO se decide acá: se elige en los Secrets (ver
# nucleo/modelo.py). Acá solo van los valores por defecto y la base de
# Google, que es fija y pública.
#
# Nombres verificados en la documentación de cada proveedor (sep-2026).
# Si un nombre cambia, se corrige en los Secrets sin tocar código, y la
# app puede listar los modelos reales del proveedor para no adivinar.
MODELO_DEFECTO_ANTHROPIC = "claude-sonnet-5"
# OJO: el nombre por defecto es solo un punto de partida. Google renombra,
# retira y balancea modelos con frecuencia, y un modelo puede estar en la
# lista y aun así no atender conversación. Por eso el modelo se elige y se
# PRUEBA desde Documentos → Mantenimiento, sin tocar los Secrets.
MODELO_DEFECTO_GOOGLE = "gemini-flash-latest"
BASE_GOOGLE_OPENAI = "https://generativelanguage.googleapis.com/v1beta/openai"

# Modelos que el admin puede elegir en pantalla, por proveedor.
MODELOS_SUGERIDOS = {
    "anthropic": {
        "claude-sonnet-5": "Sonnet 5 · rápido y suficiente para el día a día",
        "claude-opus-5": "Opus 5 · para análisis largos y difíciles",
    },
    "openai_compatible": {},   # se consultan al proveedor en Mantenimiento
}
MAX_TOKENS_RESPUESTA = 4000

# ── Índice y recuperación ────────────────────────────────────────────
# Fragmentos de ~1.200 caracteres con 200 de solape: un párrafo completo
# de un plan cabe entero y el solape evita cortar una idea por la mitad.
TAM_FRAGMENTO = 1200
SOLAPE_FRAGMENTO = 200
TOP_K_DEFECTO = 12          # fragmentos que se le pasan al modelo
TOP_K_MAX = 30
MAX_CARACTERES_CONTEXTO = 120_000   # techo duro de lo que viaja en el prompt

# Extensiones que la app sabe leer. Lo que no esté acá se rechaza
# DICIENDO POR QUÉ (no se guarda un archivo del que no podemos extraer
# texto: quedaría en la lista aparentando que la IA lo conoce).
EXTENSIONES_SOPORTADAS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xlsm",
    ".csv", ".txt", ".md", ".html", ".htm", ".json",
}
TAM_MAX_MB = 50

# ── Roles ────────────────────────────────────────────────────────────
# admin      : sube documentos, edita las instrucciones, ve el uso.
# colaborador: conversa y ve las fuentes. No carga ni borra.
ROLES = ("admin", "colaborador")

# Usuario de emergencia SOLO para el primer arranque local, cuando aún no
# hay secrets configurados. En la nube SIEMPRE se usan los secrets.
USUARIOS_DEFECTO = {
    "admin": {"clave": "sbc2026", "rol": "admin"},
}

# ── Paleta SBC (la misma de sbc_ventas, para que se vean hermanas) ───
COLOR_PRIMARIO = "#1f4e79"
COLOR_ACENTO = "#3b82f6"
COLOR_OK = "#10b981"
COLOR_ALERTA = "#dc2626"
COLOR_GRIS = "#94a3b8"

# ── Zona horaria ─────────────────────────────────────────────────────
# datetime.now() en Streamlit Cloud devuelve la hora del contenedor (UTC):
# una carga de las 07:32 se veía 14:32. Todos los sellos usan Bogotá.
TZ_BOGOTA = "America/Bogota"
