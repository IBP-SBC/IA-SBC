"""
Extrae el Nuevo Testamento de un USFX (open-bibles) a CSV por versículo.
Uso: python3 -I extraer_nt.py <archivo.usfx.xml> <salida.csv>
"""
import csv, re, sys
import xml.etree.ElementTree as ET

ruta, salida = sys.argv[1], sys.argv[2]

# Código USFX → (nombre corto en español, orden canónico de 66 libros).
# El archivo trae "San Mateo" y "San Lucas" pero "Marcos" y "Juan": se
# unifica con el nombre corto. La identidad es el código, no el nombre.
NT = [("MAT","Mateo"),("MRK","Marcos"),("LUK","Lucas"),("JHN","Juan"),
      ("ACT","Hechos"),("ROM","Romanos"),("1CO","1 Corintios"),("2CO","2 Corintios"),
      ("GAL","Gálatas"),("EPH","Efesios"),("PHP","Filipenses"),("COL","Colosenses"),
      ("1TH","1 Tesalonicenses"),("2TH","2 Tesalonicenses"),("1TI","1 Timoteo"),
      ("2TI","2 Timoteo"),("TIT","Tito"),("PHM","Filemón"),("HEB","Hebreos"),
      ("JAS","Santiago"),("1PE","1 Pedro"),("2PE","2 Pedro"),("1JN","1 Juan"),
      ("2JN","2 Juan"),("3JN","3 Juan"),("JUD","Judas"),("REV","Apocalipsis")]

raiz = ET.parse(ruta).getroot()
libros = {b.get("id"): b for b in raiz.iter("book")}
filas = []

for i, (cod, nombre) in enumerate(NT):
    orden = 40 + i
    libro = libros[cod]
    estado = {"cap": None, "ver": None, "buf": [], "dentro": False}

    def volcar():
        if estado["cap"] is not None and estado["ver"] is not None and estado["buf"]:
            texto = re.sub(r"\s+", " ", "".join(estado["buf"])).strip()
            texto = re.sub(r"\s+([,;:.!?])", r"\1", texto)
            if texto:
                filas.append(("RV1909", nombre, orden, int(estado["cap"]),
                              int(estado["ver"]), texto))
        estado["buf"] = []

    def recorrer(el):
        tag = el.tag
        if tag == "c":
            volcar(); estado["cap"] = el.get("id"); estado["ver"] = None; estado["dentro"] = False
        elif tag == "v":
            volcar(); estado["ver"] = el.get("id"); estado["dentro"] = True
        elif tag == "ve":
            volcar(); estado["dentro"] = False
        elif tag in ("f", "x", "h", "toc", "id", "s") or el.get("sfm") in ("mt", "s", "r"):
            if el.tail and estado["dentro"]:
                estado["buf"].append(el.tail)
            return
        else:
            if el.text and estado["dentro"]:
                estado["buf"].append(el.text)
            for h in el:
                recorrer(h)
        if el.tail and estado["dentro"] and tag != "ve":
            estado["buf"].append(el.tail)

    for h in libro:
        recorrer(h)
    volcar()

# ── Notas finales de las epístolas ───────────────────────────────────
# La edición de 1909 (como la King James) imprime al cierre de las cartas
# de Pablo y de Hebreos una nota de origen: "Fué escrita de Corinto á los
# Romanos…". NO es texto bíblico: es una añadidura tardía de copistas que
# las ediciones modernas omiten. El archivo fuente la pega DENTRO del
# último versículo. Se corta exactamente después del último "Amén." del
# versículo final de estos 14 libros; si alguno no tiene esa forma, el
# script se detiene en vez de cortar a ciegas.
CON_NOTA_FINAL = ["Romanos", "1 Corintios", "2 Corintios", "Gálatas", "Efesios",
                  "Filipenses", "Colosenses", "1 Tesalonicenses", "2 Tesalonicenses",
                  "1 Timoteo", "2 Timoteo", "Tito", "Filemón", "Hebreos"]
ultimo = {}
for k, r in enumerate(filas):
    clave = (r[3], r[4])
    if r[1] not in ultimo or clave > filas[ultimo[r[1]]][3:5]:
        ultimo[r[1]] = k
retiradas = []
for libro in CON_NOTA_FINAL:
    k = ultimo[libro]
    version, nombre, orden, cap, ver, texto = filas[k]
    corte = texto.rfind("Amén.")
    resto = texto[corte + len("Amén."):].strip() if corte >= 0 else ""
    if corte < 0 or not resto:
        sys.exit(f"ERROR: {libro} {cap}:{ver} no termina en 'Amén. <nota>': {texto[-90:]!r}")
    filas[k] = (version, nombre, orden, cap, ver, texto[:corte + len("Amén.")])
    retiradas.append(f"{libro} {cap}:{ver} · {resto}")
print(f"Notas finales retiradas: {len(retiradas)}")
for r in retiradas:
    print("  -", r)

with open(salida, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["version", "libro", "orden", "capitulo", "versiculo", "texto"])
    w.writerows(filas)
print(f"{len(filas)} versículos · {len(set((r[1], r[3]) for r in filas))} capítulos · "
      f"{len(set(r[1] for r in filas))} libros")
