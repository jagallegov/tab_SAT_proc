"""Convierte los insumos de INSUMOS/ en los pickles que leen los scripts del modelo.

Uso: python3 preparar_insumos.py <carpeta INSUMOS> <carpeta de trabajo>

Incluye a los estudiantes que el archivo de matrícula original (20262S.xlsx) no traía y que sí
están en la exportación nueva (20262S-2.xlsx), por ejemplo los PAET de Enfermería y Farmacia
que se matriculan por la sede Bogotá. Se traducen al formato de columnas del archivo original y
se les agregan sus notas parciales de la exportación nueva (sede Bogotá).
Los estudiantes que ya estaban conservan los datos del archivo original.
"""
import sys, glob, os, json
import numpy as np, pandas as pd

ins, out = sys.argv[1:3]
os.makedirs(out, exist_ok=True)
leer = lambda f, **k: pd.read_excel(f, sheet_name="Sheet2", header=1, **k)

# ---------------------------------------------------------------- matrícula histórica
frames = []
for f in sorted(glob.glob(f"{ins}/MATRICULA/2*S.xlsx")):
    d = leer(f); d["ARCHIVO"] = os.path.basename(f); frames.append(d)
    print(os.path.basename(f), d.shape)
orig = frames[-1]                       # 20262S.xlsx, el periodo en curso
assert orig.PERIODO.iloc[0] == "2026-02", orig.PERIODO.iloc[0]

# ---------------------------------------------------------------- estudiantes que faltaban
nueva = leer(f"{ins}/MATRICULA/20262S-2.xlsx")
for d in (orig, nueva): d["DOCUMENTO"] = d.DOCUMENTO.astype(str)
falt = nueva[(~nueva.DOCUMENTO.isin(set(orig.DOCUMENTO))) & (nueva.NIVEL == "PREGRADO") & (nueva.PERIODO == "2026-2S")]
falt = falt.drop_duplicates(["DOCUMENTO", "COD_PLAN"]).copy()

FAC = {"FACULTAD PAET BOG-MED ENFERMERIA": "FACULTAD DE CIENCIAS DE LA VIDA", "FACULTAD PAET BOG-MED CIENCIAS": "FACULTAD DE CIENCIAS DE LA VIDA"}
def facultad(f):
    if f in FAC: return FAC[f]
    if f.startswith("FACULTAD PAET") and f.endswith("MINAS"): return "FACULTAD DE MINAS"
    if f.startswith("FACULTAD PAET") and f.endswith("ARQUITECTURA"): return "FACULTAD DE ARQUITECTURA"
    return f
def per_viejo(p): return p.replace("-1S", "-01").replace("-2S", "-03")
def num(v):
    if pd.isna(v): return None
    try: return str(int(float(v))) if float(v) == int(float(v)) else str(v)
    except (TypeError, ValueError): return str(v)

n = pd.DataFrame(index=falt.index, columns=[c for c in orig.columns])
dir_ = lambda c: falt[c] if c in falt else np.nan
n["PERIODO"] = "2026-02"; n["SEDE"] = falt.SEDE; n["COD_FACULTAD"] = falt.COD_FACULTAD
n["FACULTAD"] = falt.FACULTAD.map(facultad); n["UAB"] = falt.UAB; n["TIPONIVEL"] = "PRE"; n["NIVEL"] = falt.NIVEL
n["PROGRAMA_CURRICULAR"] = falt.PROGRAMA_CURRICULAR; n["PLAN"] = falt.COD_PLAN; n["CARRERA"] = falt.PROGRAMA_CURRICULAR
n["EXP"] = falt.EXPEDIENTE; n["CONVOCATORIA"] = falt.CONVOCATORIA.map(per_viejo); n["APERTURA"] = falt.APERTURA.map(per_viejo)
n["T_DOCUMENTO"] = falt.T_DOCUMENTO.map({"C": "CC", "T": "TI", "O": "PT", "E": "CE", "P": "PS"}).fillna(falt.T_DOCUMENTO)
n["DOCUMENTO"] = falt.DOCUMENTO; n["NOMBRES"] = falt.NOMBRES_LEGAL
n["APELLIDOS"] = (falt.APELLIDO1_LEGAL.fillna("") + " " + falt.APELLIDO2_LEGAL.fillna("")).str.strip()
n["PEAMA"] = "NO"; n["ACCESO"] = falt.ACCESO; n["SUBACCESO"] = falt.SUBACCESO; n["NODO_INICIO"] = falt.NODO_INICIO
n["EDAD"] = falt.EDAD; n["SEXO"] = falt.SEXO_LEGAL.map({"Masculino": "M", "Femenino": "F"}); n["GENERO"] = falt.GENERO
n["CORREO"] = falt.CORREO; n["TELEFONO"] = dir_("TEL_RESIDENCIA"); n["DIRECCION"] = dir_("DIRECCION_RESIDENCIA")
n["ESTRATO"] = falt.ESTRATO.map(num); n["PBM"] = falt.PBM
n["TIPCOLEGIO"] = falt.TIPCOLEGIO; n["NOMBRE_COLEGIO"] = falt.NOMBRE_COLEGIO
n["EXTRANJERO"] = falt.EXTRANJERO.map({"NO": "N", "SI": "S"}).fillna(falt.EXTRANJERO)
n["CODIGO_PAIS_DE_NACIMIENTO"] = falt.COD_PAIS_NACIMIENTO; n["PAIS_NACIMIENTO"] = falt.PAIS_NACIMIENTO; n["NACIONALIDAD"] = falt.PAIS_NACIMIENTO
n["COD_DEPARTAMENTO_NAC"] = falt.COD_DEPARTAMENTO_NACIMIENTO; n["ID_MUNICIPIO_NACIMIENTO"] = falt.COD_MUNICIPIO_NACIMIENTO
n["DEP_RESIDENCIA"] = dir_("DEPARTAMENTO_RESIDENCIA"); n["MUN_RESIDENCIA"] = dir_("MUNICIPIO_RESIDENCIA")
n["COD_DEPT_PROCEDENCIA"] = falt.COD_DEPARTAMENTO_PROCEDENCIA; n["DEP_PROCEDENCIA"] = falt.DEPARTAMENTO_PROCEDENCIA
n["COD_MUNIC_PROCEDENCIA"] = falt.COD_MUNICIPIO_PROCEDENCIA; n["MUN_PROCEDENCIA"] = falt.MUNICIPIO_PROCEDENCIA
n["DEP_NACIMIENTO"] = falt.DEPARTAMENTO_NACIMIENTO; n["MUN_NACIMIENTO"] = falt.MUNICIPIO_NACIMIENTO
n["FECHA_NACIMIENTO"] = pd.to_datetime(falt.FECHA_NACIMIENTO, errors="coerce").dt.strftime("%d/%m/%Y")
n["OPCION_GRA"] = "NO"; n["TRASLADADO"] = "N"; n["MATRICULAS"] = falt.MATRICULAS; n["ARCHIVO"] = "20262S-2.xlsx"
for c in ("EDAD", "MATRICULAS", "PBM"): n[c] = pd.to_numeric(n[c], errors="coerce")
n = n.astype(orig.dtypes.to_dict(), errors="ignore")

mat = pd.concat(frames[:-1] + [orig, n], ignore_index=True)
mat["DOCUMENTO"] = mat.DOCUMENTO.astype(str)
mat["PLAN"] = mat.PLAN.astype(str)   # el reporte de bloqueos trae COD_PLAN como texto
mat.to_pickle(f"{out}/matricula.pkl")
print("matrícula", mat.shape, "agregados", len(n), n.FACULTAD.value_counts().to_dict())

# ---------------------------------------------------------------- bloqueos
blq = leer(f"{ins}/BLOQUEOS/99999_RE_EST_BLQ_ACR_291026.xlsx"); blq["DOCUMENTO"] = blq.DOCUMENTO.astype(str); blq["COD_BLOQUEO"] = pd.to_numeric(blq.COD_BLOQUEO, errors="coerce").astype("Int64").astype(str); blq["COD_PLAN"] = blq.COD_PLAN.astype(str); blq.to_pickle(f"{out}/bloqueos.pkl")

# ---------------------------------------------------------------- notas parciales
hist = []
for f in sorted(glob.glob(f"{ins}/NOTAS PARCIALES/2*_RE_ASI_EST_NOT_PAR_291026.xlsx")):
    if os.path.basename(f).startswith("20262"): continue
    d = leer(f); hist.append(d); print(os.path.basename(f), d.shape)
nh = pd.concat(hist, ignore_index=True); nh["DOCUMENTO"] = nh.DOCUMENTO.astype(str); nh.to_pickle(f"{out}/notas.pkl")
cur = leer(f"{ins}/NOTAS PARCIALES/20262_RE_ASI_EST_NOT_PAR_291026.xlsx")
cur_b = leer(f"{ins}/NOTAS PARCIALES/20262_RE_ASI_EST_NOT_PAR_291026-2.xlsx")
for d in (cur, cur_b): d["DOCUMENTO"] = d.DOCUMENTO.astype(str)
extra = cur_b[cur_b.DOCUMENTO.isin(set(n.DOCUMENTO))]
cur_all = pd.concat([cur, extra], ignore_index=True).drop_duplicates(["DOCUMENTO", "COD_ASIGNATURA", "GRUP_ACTA", "DESC_PRUEBA", "PORCENTAJE"])
cur_all.to_pickle(f"{out}/notas_20262.pkl")
print("notas 2026-2S", cur.shape, "+", len(extra), "->", cur_all.shape)

pd.to_pickle(sorted(set(n.DOCUMENTO)), f"{out}/agregados_docs.pkl")   # el modelo de notas los excluye al calibrar, para no mover a quienes ya estaban
resumen = {"agregados": int(len(n)), "por_facultad": n.FACULTAD.value_counts().to_dict(), "por_programa": n.PROGRAMA_CURRICULAR.value_counts().to_dict(),
           "con_notas": int(n.DOCUMENTO.isin(set(cur_all.DOCUMENTO)).sum()), "sin_notas": int((~n.DOCUMENTO.isin(set(cur_all.DOCUMENTO))).sum())}
json.dump(resumen, open(f"{out}/agregados.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(resumen, ensure_ascii=False))
