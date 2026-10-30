"""Genera los módulos de datos de la ventanilla de consulta a partir del Excel de
riesgo (ENTREGABLES) y del reporte de notas parciales de 2026-2S (INSUMOS).
Uso: python3 etl_ventanilla.py <riesgo.xlsx> <notas_2026-2S.xlsx> <carpeta_salida>"""
import sys, json, re
import numpy as np, pandas as pd

riesgo, notas, salida = sys.argv[1:4]
E = pd.read_excel(riesgo, sheet_name="Matricula 2026-2S")
A = pd.read_excel(riesgo, sheet_name="Todas las asignaturas")
N = pd.read_pickle(notas) if notas.endswith(".pkl") else pd.read_excel(notas, sheet_name="Sheet2", header=1)
N = N[N.ANULADA.astype(str).str.upper().eq("N") & N.TIPO_NIVEL.astype(str).str.upper().eq("PREGRADO")].copy()
N["COD_ASIGNATURA"] = N.COD_ASIGNATURA.astype(str)
A["COD_ASIGNATURA"] = A.COD_ASIGNATURA.astype(str)

CONECT = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "a", "al", "para", "por", "con", "o", "u"}
ACRO = {"PEAMA", "PAES", "PAET", "UNAL", "SENA", "STEM", "STEAM", "UNESCO", "IED", "I.E."}
ROMANOS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
def _mayus1(w): return re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", lambda m: m.group(0).upper(), w, count=1)
def tit(s):
    """Pasa a tipo título (conectores en minúscula, numerales romanos en mayúscula)."""
    out = []
    for i, w in enumerate(str(s).split()):
        l = w.lower()
        out.append(w.upper() if (w.upper() in ROMANOS or w.upper() in ACRO) else l if (i > 0 and l in CONECT) else _mayus1(l))
    return " ".join(out)
def nom(s):
    if pd.isna(s): return ""
    t = " ".join(str(s).split())
    return tit(t) if t.isupper() else t
def r(x, k=1): return None if pd.isna(x) else round(float(x), k)

# ---- estudiante x asignatura: promedio ponderado de los parciales calificados
# La fila P01 al 100 por ciento es el acumulado del SIA, no un parcial: no cuenta como calificada.
# Parcial calificado = porcentaje entre 0 y 100 (exclusive) con nota registrada, igual que en el modelo.
N["w"] = pd.to_numeric(N.PORCENTAJE, errors="coerce")
claves = ["DOCUMENTO", "COD_ASIGNATURA", "GRUP_ACTA"]
base = N.groupby(claves, as_index=False).agg(asignatura=("ASIGNATURA", "first"), uab=("UAB", "first"), tip=("TIPOLOGIA", "first"), doc=("NOM_DOCEN_PRINCI", "first"))
P = N[(N.w > 0) & (N.w < 100)].copy()
P["cal"] = P.CALIFICACION_P.notna(); P["nw"] = P.CALIFICACION_P * P.w
P["wc"] = np.where(P.cal, P.w, 0.0)
gp = P.groupby(claves, as_index=False).agg(pct=("wc", "sum"), num=("nw", "sum"), ncal=("cal", "sum"), npar=("cal", "size"))
g = base.merge(gp, on=claves, how="left").fillna({"pct": 0, "num": 0, "ncal": 0, "npar": 0})
g["prom"] = np.where(g.pct > 0, g.num / g.pct, np.nan)
g["rank"] = g.groupby(["COD_ASIGNATURA", "GRUP_ACTA"]).prom.rank(pct=True, method="average")
g["ngr"] = g.groupby(["COD_ASIGNATURA", "GRUP_ACTA"]).prom.transform("count")
g["med"] = g.groupby(["COD_ASIGNATURA", "GRUP_ACTA"]).prom.transform("median")
g["q1"] = ((g["rank"] <= .25) & (g.ngr >= 4) & g.prom.notna()).astype(int)

# ---- catálogos
niv = {"Bajo": 0, "Medio": 1, "Alto": 2}
E["DOCUMENTO"] = E.DOCUMENTO.astype(str)
g["DOCUMENTO"] = g.DOCUMENTO.astype(str)
E = E.drop_duplicates("DOCUMENTO")
E["PROGRAMA_CURRICULAR"] = E.PROGRAMA_CURRICULAR.map(nom); E["FACULTAD"] = E.FACULTAD.map(nom)
progs = sorted(E.PROGRAMA_CURRICULAR.dropna().unique()); facs = sorted(E.FACULTAD.dropna().unique())
pi = {p: i for i, p in enumerate(progs)}; fi = {f: i for i, f in enumerate(facs)}
sen = E.SENALES_RIESGO.fillna("").str.split("; ").explode(); sen = sen[sen != ""]
sen = sen.str.replace("Bloqueo académico", "Bloqueo", regex=False).str.replace(r"Parciales en el cuarto inferior.*", "Parciales en el cuarto inferior del grupo", regex=True)
sen = sen.str.replace(r"Rezago de \d+ semestres", "Rezago de 2 o más semestres", regex=True)
sens = sen.value_counts().index.tolist(); si = {s: i for i, s in enumerate(sens)}
def codif(txt):
    out = set()
    for s in str(txt).split("; "):
        s = s.replace("Bloqueo académico", "Bloqueo")
        s = re.sub(r"Parciales en el cuarto inferior.*", "Parciales en el cuarto inferior del grupo", s)
        s = re.sub(r"Rezago de \d+ semestres", "Rezago de 2 o más semestres", s)
        if s in si: out.add(si[s])
    return sorted(out)

est = []
for x in E.itertuples():
    est.append([x.DOCUMENTO, tit(" ".join(f"{x.NOMBRES} {x.APELLIDOS}".split())), pi[x.PROGRAMA_CURRICULAR], fi[x.FACULTAD],
                niv[x.NIVEL_RIESGO], r(x.VALOR_RIESGO), r(x.VALOR_RIESGO_BASE),
                int(x.MATRICULAS) if pd.notna(x.MATRICULAS) else None,
                int(x.ASIGNATURAS_INSCRITAS) if pd.notna(x.ASIGNATURAS_INSCRITAS) else 0,
                int(x.ASIGNATURAS_CON_PARCIAL) if pd.notna(x.ASIGNATURAS_CON_PARCIAL) else 0,
                int(x.EDAD) if pd.notna(x.EDAD) else None, codif(x.SENALES_RIESGO)])

# asignaturas por estudiante
eidx = {d: i for i, d in enumerate(E.DOCUMENTO)}
g = g[g.DOCUMENTO.isin(eidx)]
acod = sorted(g.COD_ASIGNATURA.unique()); ai = {c: i for i, c in enumerate(acod)}
rows = [[eidx[x.DOCUMENTO], ai[x.COD_ASIGNATURA], str(x.GRUP_ACTA), r(x.prom, 2), r(x.med, 2),
         r(x.pct, 0), int(x.ncal), int(x.npar), int(x.q1), int(x.ngr)] for x in g.itertuples()]

# resumen por asignatura: matriculados por nivel de riesgo + indicadores históricos
niv_arr = E.NIVEL_RIESGO.map(niv).values
g["nivel"] = niv_arr[g.DOCUMENTO.map(eidx).values]
cnt = g.pivot_table(index="COD_ASIGNATURA", columns="nivel", values="DOCUMENTO", aggfunc="nunique", fill_value=0)
for k in (0, 1, 2):
    if k not in cnt: cnt[k] = 0
meta = g.groupby("COD_ASIGNATURA").agg(asignatura=("asignatura", "first"), uab=("uab", "first"), tip=("tip", "first"),
    insc=("DOCUMENTO", "nunique"), conp=("ncal", lambda s: int((s > 0).sum())), bajo3=("prom", lambda s: int((s < 3).sum())),
    prom=("prom", "mean"), grupos=("GRUP_ACTA", "nunique"))
A2 = A.drop_duplicates("COD_ASIGNATURA").set_index("COD_ASIGNATURA")
asig = []
for c in acod:
    m = meta.loc[c]; h = A2.loc[c] if c in A2.index else None
    asig.append([c, nom(m.asignatura), nom(m.uab), m.tip, int(m.insc), int(m.grupos),
                 int(cnt.loc[c, 2]), int(cnt.loc[c, 1]), int(cnt.loc[c, 0]), int(m.conp), int(m.bajo3), r(m.prom, 2),
                 r(h.PCT_PERDIDA_HISTORICA) if h is not None else None,
                 int(h.ESTUDIANTES_2024_2S_A_2025_2S) if h is not None and pd.notna(h.ESTUDIANTES_2024_2S_A_2025_2S) else None])

meta_js = {"progs": progs, "facs": facs, "senales": sens,
           "prog_fac": [fi[E[E.PROGRAMA_CURRICULAR == p].FACULTAD.iloc[0]] for p in progs],
           "corte": "29/10/2026", "periodo": "2026-2S",
           "cortes": [5, 15]}
def w(nombre, var, obj):
    open(f"{salida}/{nombre}", "w", encoding="utf-8").write(f"window.{var}=" + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";")
w("sat_meta.js", "SAT_META", meta_js)
w("sat_est.js", "SAT_EST", est)
w("sat_asig.js", "SAT_ASIG", asig)
w("sat_notas.js", "SAT_NOTAS", rows)
print("estudiantes", len(est), "asignaturas", len(asig), "filas est-asig", len(rows))
print(pd.Series(niv_arr).value_counts().to_dict())


# ---------------------------------------------------------------- ficha del estudiante
def f_txt(v): return None if pd.isna(v) or str(v).strip() == "" else nom(v)
def f_mail(v): return None if pd.isna(v) or str(v).strip() == "" else str(v).strip().lower()
def f_raw(v): return None if pd.isna(v) or str(v).strip() == "" else " ".join(str(v).split())
def f_sn(v):
    if pd.isna(v): return None
    return {"S": "Sí", "SI": "Sí", "SÍ": "Sí", "N": "No", "NO": "No"}.get(str(v).strip().upper(), nom(v))
def f_num(d):
    def f(v):
        if pd.isna(v): return None
        return f"{float(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f
def f_dinero(v):
    return None if pd.isna(v) else "$ " + f"{float(v):,.0f}".replace(",", ".")
def f_cod(v):
    if pd.isna(v): return None
    try: return str(int(float(v)))
    except Exception: return str(v)
def f_mapa(m):
    return lambda v: None if pd.isna(v) else m.get(str(v).strip().upper(), nom(v))
def f_periodo(v):
    if pd.isna(v): return None
    a, b = str(v).split("-"); return f"{a}-{int(b)}S"
def f_nivelar(v):
    if pd.isna(v): return None
    return " ".join(str(v).split()).replace("Estudiantes que ", "", 1).capitalize()
def f_lista(v):
    if pd.isna(v) or not str(v).strip(): return None
    return ", ".join(tit(x.strip().lower()) for x in str(v).split(","))

CAMPOS = [
 ("Datos personales", [("Tipo de documento", "T_DOCUMENTO", f_mapa({"CC": "Cédula de ciudadanía", "TI": "Tarjeta de identidad", "CE": "Cédula de extranjería", "PS": "Pasaporte"})),
   ("Documento", "DOCUMENTO", f_cod), ("Nombres", "NOMBRES", lambda v: None if pd.isna(v) else tit(" ".join(str(v).split()))),
   ("Apellidos", "APELLIDOS", lambda v: None if pd.isna(v) else tit(" ".join(str(v).split()))),
   ("Sexo", "SEXO", f_mapa({"M": "Masculino", "F": "Femenino"})), ("Género", "GENERO", f_txt),
   ("Fecha de nacimiento", "FECHA_NACIMIENTO", f_raw), ("Edad", "EDAD", f_cod),
   ("Nacionalidad", "NACIONALIDAD", f_txt), ("Segunda nacionalidad", "SEGUNDA_NACIONALIDAD", f_txt), ("Extranjero", "EXTRANJERO", f_sn)]),
 ("Contacto", [("Correo institucional", "CORREO", f_mail), ("Correo alterno", "CORREO_ALTERNO", f_mail), ("Teléfono", "TELEFONO", f_cod),
   ("Dirección", "DIRECCION", f_txt), ("Departamento de residencia", "DEP_RESIDENCIA", f_txt), ("Municipio de residencia", "MUN_RESIDENCIA", f_txt)]),
 ("Origen", [("País de nacimiento", "PAIS_NACIMIENTO", f_txt), ("Departamento de nacimiento", "DEP_NACIMIENTO", f_txt), ("Municipio de nacimiento", "MUN_NACIMIENTO", f_txt),
   ("Departamento de procedencia", "DEP_PROCEDENCIA", f_txt), ("Municipio de procedencia", "MUN_PROCEDENCIA", f_txt)]),
 ("Programa curricular", [("Sede", "SEDE", f_txt), ("Periodo", "PERIODO", f_periodo), ("Nivel", "NIVEL", f_txt), ("Facultad", "FACULTAD", f_txt), ("Unidad académica básica", "UAB", f_txt),
   ("Programa curricular", "PROGRAMA_CURRICULAR", f_txt), ("Plan de estudios", "PLAN", f_cod), ("Código SNIES", "SNIES", f_cod),
   ("Expediente", "EXP", f_cod), ("Código", "CODIGO", f_cod), ("Número de matrículas", "MATRICULAS", f_cod),
   ("Opción de grado", "OPCION_GRA", f_sn), ("Trasladado", "TRASLADADO", f_sn), ("Cancelación", "CANCELACION", f_txt)]),
 ("Admisión", [("Convocatoria", "CONVOCATORIA", f_raw), ("Apertura", "APERTURA", f_raw), ("Tipo de acceso", "ACCESO", f_txt), ("Subacceso", "SUBACCESO", f_txt),
   ("Nivelación al ingresar", "NODO_INICIO", f_nivelar), ("PEAMA", "PEAMA", f_sn), ("Etapa PEAMA", "ETAPA_PEAMA", f_txt)]),
 ("Condición socioeconómica y puntajes", [("Estrato", "ESTRATO", f_txt), ("Puntaje básico de matrícula (PBM)", "PBM", f_cod), ("Indicador A3", "INDICADOR_A3", f_num(2)),
   ("Indicador B2", "INDICADOR_B2", f_num(2)), ("MPVZ", "MPVZ", f_sn), ("Valor de financiación MEN (662)", "VALOR_FIN_MEN_662", f_dinero)]),
 ("Colegio", [("Tipo de colegio", "TIPCOLEGIO", f_mapa({"OFI": "Oficial", "PRV": "Privado"})), ("Código del colegio", "COD_COLEGIO", f_cod), ("Nombre del colegio", "NOMBRE_COLEGIO", f_txt)]),
 ("Riesgo en el periodo", [("Asignaturas inscritas", "ASIGNATURAS_INSCRITAS", f_cod), ("Asignaturas con parcial calificado", "ASIGNATURAS_CON_PARCIAL", f_cod),
   ("Asignaturas con parcial en el cuarto inferior del grupo", "ASIG_PARCIAL_BAJO_GRUPO", f_lista)]),
]
E0 = pd.read_excel(riesgo, sheet_name="Matricula 2026-2S").drop_duplicates("DOCUMENTO")
E0["DOCUMENTO"] = E0.DOCUMENTO.astype(str)
assert list(E0.DOCUMENTO) == list(E.DOCUMENTO)
campos_meta, cols_vals = [], []
for gi, (g, lst) in enumerate(CAMPOS):
    for et, col, fn in lst:
        vals = [fn(v) for v in E0[col]]
        if all(v is None for v in vals): continue
        u = sorted({v for v in vals if v is not None})
        if len(u) <= 800:
            ix = {v: i for i, v in enumerate(u)}
            campos_meta.append([gi, et, u]); cols_vals.append([ix[v] if v is not None else -1 for v in vals])
        else:
            campos_meta.append([gi, et, None]); cols_vals.append(vals)
filas = [list(x) for x in zip(*cols_vals)]
w("sat_ficha.js", "SAT_FICHA", {"grupos": [g for g, _ in CAMPOS], "campos": campos_meta, "filas": filas})

# ---------------------------------------------------------------- asignaturas con más de 70 de pérdida
Ac = A.drop_duplicates("COD_ASIGNATURA").set_index("COD_ASIGNATURA")
pb3 = meta.bajo3 / meta.conp.where(meta.conp > 0) * 100      # avance 2026-2S con las notas vigentes
codigos = sorted(set(Ac.index[Ac.PCT_PERDIDA_HISTORICA > 70]) | set(pb3.index[pb3 > 70]))
def ni(v): return None if pd.isna(v) else int(v)
uab_notas = base.drop_duplicates("COD_ASIGNATURA").set_index("COD_ASIGNATURA").uab
riesgo_asig = []
for c in codigos:
    h = Ac.loc[c] if c in Ac.index else None
    m = meta.loc[c] if c in meta.index else None
    uab_x = nom(uab_notas[c]) if c in uab_notas.index else nom(h.UAB)
    hv = (lambda k: h[k]) if h is not None else (lambda k: np.nan)
    riesgo_asig.append([c, nom(m.asignatura if m is not None else h.ASIGNATURA), uab_x, (m.tip if m is not None else h.TIPOLOGIA),
        hv("PERIODOS") if isinstance(hv("PERIODOS"), str) else "", ni(hv("ESTUDIANTES_2024_2S_A_2025_2S")), ni(hv("PERDIERON")), r(hv("PCT_PERDIDA_HISTORICA")),
        r(hv("PCT_2024-2S")), r(hv("PCT_2025-1S")), r(hv("PCT_2025-2S")),
        int(m.insc) if m is not None else None, int(m.conp) if m is not None else None, r(pb3.get(c)),
        int(cnt.loc[c, 2]) if c in cnt.index else None, int(cnt.loc[c, 1]) if c in cnt.index else None])
w("sat_riesgo.js", "SAT_RIESGO", riesgo_asig)
print("ficha campos", len(campos_meta), "riesgo asig", len(riesgo_asig))


# ---------------------------------------------------------------- porcentaje con nota bajo 3,0 en cada parcial (al corte)
P2 = P[P.cal].copy()
P2["bajo"] = (P2.CALIFICACION_P < 3.0).astype(int)
cols_p = sorted(P2.DESC_PRUEBA.dropna().unique())[:3]
pp = P2[P2.DESC_PRUEBA.isin(cols_p)].groupby(["COD_ASIGNATURA", "DESC_PRUEBA"]).agg(n=("bajo", "size"), b=("bajo", "sum")).reset_index()
info = base.drop_duplicates("COD_ASIGNATURA").set_index("COD_ASIGNATURA")
filas_p = []
for c, d in pp.groupby("COD_ASIGNATURA"):
    m = {x.DESC_PRUEBA: [int(x.n), int(x.b)] for x in d.itertuples()}
    filas_p.append([c, nom(info.loc[c, "asignatura"]), nom(info.loc[c, "uab"]), [m.get(k) for k in cols_p]])
w("sat_parciales.js", "SAT_PARCIALES", {"parciales": cols_p, "filas": filas_p})
print("parciales", cols_p, "asignaturas", len(filas_p))
