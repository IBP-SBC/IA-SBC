"""
Validación AST: (1) nombres usados que no están importados ni definidos
(el NameError que py_compile NO detecta) y (2) keys de widget duplicadas
(StreamlitDuplicateElementKey).
"""
import ast
import builtins
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent / 'src'
BUILTINS = set(dir(builtins))


def definidos(tree):
    """Nombres que el módulo define o importa a nivel de archivo y de función."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(n, ast.Lambda):
                out.add(n.name)
            args = n.args
            for a in (list(args.args) + list(args.posonlyargs)
                      + list(args.kwonlyargs)):
                out.add(a.arg)
            if args.vararg:
                out.add(args.vararg.arg)
            if args.kwarg:
                out.add(args.kwarg.arg)
        elif isinstance(n, ast.ClassDef):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.comprehension,)):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(n, ast.Global):
            out.update(n.names)
    return out


def usados(tree):
    return {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _es_llamada_st(call):
    """True si la llamada es a un widget de Streamlit (st.algo(...)).

    Solo esas keys colisionan. Las funciones propias de la app reciben `key`
    como PREFIJO (selector_anio(key='ana')) y se repiten a propósito."""
    f = call.func
    return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
        and f.value.id == 'st'


def keys_widget(tree):
    """Valores literales de key= en widgets de Streamlit (duplicados = crash)."""
    ks = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _es_llamada_st(n):
            for kw in n.keywords:
                if kw.arg == 'key' and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    ks.append(kw.value.value)
    return ks


def firmas_proyecto(raiz):
    """
    Mapa {nombre_funcion: (min_args, max_args)} de las funciones definidas en
    el proyecto, para detectar llamadas con un número de argumentos imposible.

    POR QUÉ: `fmt_co(valor, 1)` no lo detecta py_compile (es sintaxis válida)
    ni el chequeo de nombres (la función existe). Solo revienta en ejecución,
    dentro de un try/except que lo convierte en un mensaje amable... y la
    sección entera desaparece de la pantalla. Pasó de verdad en la v1.7.86.
    Solo se consideran los nombres definidos UNA vez en todo el proyecto: si
    hay dos funciones con el mismo nombre, no se puede saber cuál se llama.
    """
    defs = {}
    for p in raiz.rglob('*.py'):
        try:
            t = ast.parse(p.read_text())
        except SyntaxError:
            continue
        for n in ast.walk(t):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = n.args
                pos = len(a.posonlyargs) + len(a.args)
                mn = pos - len(a.defaults)
                mx = 10**6 if a.vararg else pos
                defs.setdefault(n.name, []).append((mn, mx))
    return {k: v[0] for k, v in defs.items() if len(v) == 1}


FIRMAS = firmas_proyecto(RAIZ)


def aridad_mala(tree):
    """Llamadas con más/menos argumentos posicionales de los que acepta.

    Solo se verifican los nombres que ESTE archivo importa explícitamente o
    define él mismo. Sin ese filtro, una función local llamada `_f` se
    compararía contra la firma de otra `_f` de un módulo distinto y daría un
    falso positivo (pasó al escribir este chequeo).
    """
    visibles = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                visibles.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visibles.add(n.name)
    # Nombres reasignados o usados como parámetro: no son la función global.
    locales = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            locales.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = n.args
            for x in (list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs)):
                locales.add(x.arg)
    visibles -= locales
    malas = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Name):
            continue
        if n.func.id not in visibles:
            continue
        f = FIRMAS.get(n.func.id)
        if not f:
            continue
        if any(isinstance(a, ast.Starred) for a in n.args):
            continue
        npos = len(n.args)
        nkw = len([k for k in n.keywords if k.arg])
        mn, mx = f
        if npos > mx or (npos + nkw) < mn:
            malas.append(f"{n.func.id}() línea {n.lineno}: "
                         f"{npos} pos, acepta {mn}..{mx}")
    return malas


# ── KEYS COMPARTIDAS ENTRE MÓDULOS (v1.8.5) ─────────────────────────
# El chequeo por archivo no ve el caso real que rompió Editorial: Home.py
# registra el botón "Salir" con key '_btn_logout' antes de la navegación, y una
# PÁGINA volvió a llamar a la misma función. Dos archivos distintos, misma key,
# misma corrida → StreamlitDuplicateElementKey. Se revisa qué keys de app/ui/
# (que se ejecuta siempre) reaparecen en las páginas.
def keys_de(path):
    try:
        t = ast.parse(path.read_text())
    except SyntaxError:
        return set()
    return set(keys_widget(t))


def funciones_con_key(path):
    """Funciones de app/ui/ que registran widgets con key fija."""
    try:
        t = ast.parse(path.read_text())
    except SyntaxError:
        return {}
    out = {}
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ks = keys_widget(n)
            if ks:
                out[n.name] = ks
    return out


_ui_funcs = {}
for _f in (RAIZ / 'app' / 'ui').glob('*.py'):
    _ui_funcs.update(funciones_con_key(_f))

_choques = []
def _solo_codigo(txt):
    """Quita comentarios y docstrings: la mención de una función dentro de una
    explicación NO es una llamada. (La corrección de Editorial documenta el bug
    nombrando `exigir_login()`, y eso hacía saltar el check.)"""
    try:
        t = ast.parse(txt)
    except SyntaxError:
        return txt
    llamadas = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                llamadas.add(f.id)
            elif isinstance(f, ast.Attribute):
                llamadas.add(f.attr)
    return llamadas


_home_llama = _solo_codigo((RAIZ / 'app' / 'Home.py').read_text())
for _pg in sorted((RAIZ / 'app' / 'paginas').glob('*.py')):
    _txt = _pg.read_text()
    _pg_llama = _solo_codigo(_txt)
    for _fn, _ks in _ui_funcs.items():
        # La función se LLAMA desde la página y también desde Home.py: la key
        # quedaría registrada dos veces en la misma corrida.
        if _fn in _pg_llama and _fn in _home_llama:
            _choques.append(f"{_pg.name} llama {_fn}() y Home.py también "
                            f"(keys {_ks[:3]})")

errores = 0
if _choques:
    for _c in _choques:
        print(f"❌ KEY DUPLICADA ENTRE MÓDULOS: {_c}")
    errores += len(_choques)

for p in sorted(RAIZ.rglob('*.py')):
    src = p.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"❌ SINTAXIS {p.relative_to(RAIZ)}: {e}")
        errores += 1
        continue

    faltan = usados(tree) - definidos(tree) - BUILTINS - {'__file__', '__name__'}
    if faltan:
        print(f"❌ NOMBRES SIN DEFINIR {p.relative_to(RAIZ)}: {sorted(faltan)}")
        errores += 1

    mal = aridad_mala(tree)
    if mal:
        print(f"❌ ARIDAD {p.relative_to(RAIZ)}: {mal}")
        errores += 1

    # ── RENOMBRADO POR POSICIÓN TRAS UN GROUPBY (v1.8.16) ───────────
    # `g.columns = [...]` sobre el resultado de un groupby depende de cuántas
    # columnas devuelva pandas, y eso CAMBIA ENTRE VERSIONES: el mismo código
    # que corría acá reventó en Colab con «Length mismatch». Es el antipatrón
    # de mapear por posición, aplicado al resultado de una agregación.
    # Se avisa (no es error fatal: sobre un DataFrame propio es legítimo).
    _txt_src = src.splitlines()
    for _i, _ln in enumerate(_txt_src):
        if re.match(r'\s*[_\w]+\.columns\s*=\s*\[', _ln):
            _ctx = '\n'.join(_txt_src[max(0, _i - 6):_i])
            if 'groupby' in _ctx or 'value_counts' in _ctx:
                print(f"⚠️  RENOMBRADO POR POSICIÓN tras groupby "
                      f"{p.relative_to(RAIZ)}:{_i + 1} — usar .rename(columns=)"
                      " para no depender de la versión de pandas")

    ks = keys_widget(tree)
    dups = sorted({k for k in ks if ks.count(k) > 1})
    if dups:
        print(f"❌ KEYS DUPLICADAS {p.relative_to(RAIZ)}: {dups}")
        errores += 1

print(f"\n{'✅ Sin hallazgos' if not errores else f'❌ {errores} archivo(s) con hallazgos'}")
sys.exit(1 if errores else 0)
