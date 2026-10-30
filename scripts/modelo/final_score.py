import pandas as pd, numpy as np, warnings, json, pickle; warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score
pd.set_option("display.width",250); pd.set_option("display.max_rows",300)
import os; d=os.environ["SAT_DATA"]
df = pd.read_pickle(f"{d}/dataset_full.pkl")
S2 = ["LOGIT_P1","CON_PARCIAL","DESV_GRUPO_f","MIN_DESV_f","PCT_ASIG_Q1_f","N_ASIG_f","SIN_INSC","PCT_ASIG_CAL_f"]
NP=["2024-2S","2025-1S","2025-2S"]; LO,HI=0.05,0.15
tr = df[df.PER.isin(NP)]; g = Pipeline([("sc",StandardScaler()),("m",LogisticRegression(C=1.0,max_iter=2000))]).fit(tr[S2], tr.Y)
coef = dict(zip(S2, g.named_steps["m"].coef_[0])); sc_ = g.named_steps["sc"].scale_
coef_raw = {k: float(c/s) for k,c,s in zip(S2, g.named_steps["m"].coef_[0], sc_)}
print("coef (por unidad):", {k:round(v,3) for k,v in coef_raw.items()})
sc = df[df.PER=="2026-2S"].copy()
sc["VALOR_RIESGO_BASE"]=sc.P1; sc["VALOR_RIESGO"]=g.predict_proba(sc[S2])[:,1]
sc["NIVEL_RIESGO"]=np.where(sc.VALOR_RIESGO>=HI,"Alto",np.where(sc.VALOR_RIESGO>=LO,"Medio","Bajo"))
sc["NIVEL_BASE"]=np.where(sc.VALOR_RIESGO_BASE>=HI,"Alto",np.where(sc.VALOR_RIESGO_BASE>=LO,"Medio","Bajo"))
print("mean base", sc.VALOR_RIESGO_BASE.mean().round(4), "mean ajustado", sc.VALOR_RIESGO.mean().round(4))
print(sc.NIVEL_RIESGO.value_counts(), (sc.NIVEL_RIESGO.value_counts(normalize=True)*100).round(1))
print(pd.crosstab(sc.NIVEL_BASE, sc.NIVEL_RIESGO))
hist = df[df.PER<"2026-2S"]; prog_rate = hist.groupby("PROGRAMA_CURRICULAR").Y.mean()
cur_sc = pd.read_pickle(f"{d}/cur_sc.pkl")
# per-student list of courses below group Q1
low = cur_sc[(cur_sc.BAJO_Q1==1)].groupby("DOCUMENTO").ASIGNATURA.apply(lambda s: ", ".join(sorted(set(x.title() if x.isupper() else x for x in s))[:4]))
sc = sc.merge(low.rename("ASIG_BAJO_GRUPO"), left_on="DOCUMENTO", right_index=True, how="left")
def senales(r):
    s=[]
    if r.MATRICULAS_n==1: s.append("Primera matrícula")
    if r.DOC_TI==1: s.append("Documento TI")
    if r.EDAD_n<=18: s.append("Edad 18 o menos")
    if r.BLQ_ACAD_PER_ANTERIOR==1: s.append("Bloqueo académico en 2026-1S (reingreso)")
    if r.NO_MATRIC_PREVIO==1: s.append("No matriculado en 2026-1S")
    if r.CANCELO_PREVIO==1: s.append("Canceló 2026-1S")
    if r.BLQ_RESERVA_PER_ANTERIOR==1: s.append("Reserva de cupo en 2026-1S")
    if r.BLQ_PAPA_PREV==1: s.append("Bloqueo previo por PAPA menor a 3,0")
    if r.BLQ_CREDITOS_PREV==1: s.append("Bloqueo previo por cupo de créditos")
    if r.REZAGO>=2: s.append(f"Rezago de {int(r.REZAGO)} semestres")
    if "dos asignaturas" in str(r.NODO_INICIO): s.append("Debe nivelar dos asignaturas")
    elif "Matemáticas" in str(r.NODO_INICIO): s.append("Debe nivelar matemáticas")
    if prog_rate.get(r.PROGRAMA_CURRICULAR,0)>=0.08: s.append("Programa con bloqueo histórico alto")
    if r.ETAPA_PEAMA=="MOVILIDAD": s.append("PEAMA en etapa de movilidad")
    if r.SIN_INSC==1: s.append("Sin asignaturas en el reporte de notas")
    elif r.CON_PARCIAL==0: s.append("Sin parciales calificados aún")
    else:
        nq = int(round(r.PCT_ASIG_Q1*r.N_ASIG_CAL)) if pd.notna(r.PCT_ASIG_Q1) else 0
        if nq>0: s.append(f"Parciales en el cuarto inferior del grupo en {nq} de {int(r.N_ASIG_CAL)} asignaturas calificadas")
        if r.DESV_GRUPO<=-0.8: s.append("Parciales muy por debajo de la mediana del grupo")
    return "; ".join(s)
sc["SENALES_RIESGO"]=sc.apply(senales, axis=1)
sc.to_pickle(f"{d}/scored_final.pkl")
out={"coef_raw":coef_raw,"cutoffs":[LO,HI],"mean_base":float(sc.VALOR_RIESGO_BASE.mean()),"mean_adj":float(sc.VALOR_RIESGO.mean())}
out["niveles_2026"]=sc.groupby("NIVEL_RIESGO").agg(n=("Y","size"),esperados=("VALOR_RIESGO","sum"),p_prom=("VALOR_RIESGO","mean"),con_parcial=("CON_PARCIAL","mean")).reset_index().to_dict("records")
out["niveles_base_2026"]=sc.groupby("NIVEL_BASE").agg(n=("Y","size")).reset_index().to_dict("records")
out["cruce_niveles"]=pd.crosstab(sc.NIVEL_BASE, sc.NIVEL_RIESGO).to_dict()
def byg(col, min_n=0):
    t = sc.groupby(col).agg(n=("Y","size"),alto=("NIVEL_RIESGO",lambda s:(s=="Alto").sum()),medio=("NIVEL_RIESGO",lambda s:(s=="Medio").sum()),bajo=("NIVEL_RIESGO",lambda s:(s=="Bajo").sum()),esperados=("VALOR_RIESGO","sum"),con_parcial=("CON_PARCIAL","mean"))
    t["pct_alto"]=t.alto/t.n; t["pct_medio"]=t.medio/t.n
    h = hist[hist.PER.isin(["2025-2S","2026-1S"])].groupby(col).Y.mean().rename("tasa_hist"); return t.join(h).sort_values("pct_alto",ascending=False)
fac=byg("FACULTAD"); prog=byg("PROGRAMA_CURRICULAR"); print(fac.round(3)); print(prog.round(3).head(12))
out["por_facultad"]=fac.reset_index().to_dict("records"); out["por_programa"]=prog.reset_index().to_dict("records")
mt = sc.groupby(pd.cut(sc.MATRICULAS_n,[0,1,2,3,5,8,12,40],labels=["1","2","3","4 a 5","6 a 8","9 a 12","13 o más"])).agg(n=("Y","size"),alto=("NIVEL_RIESGO",lambda s:(s=="Alto").sum()),medio=("NIVEL_RIESGO",lambda s:(s=="Medio").sum()),pct_alto=("NIVEL_RIESGO",lambda s:(s=="Alto").mean()),pct_medio=("NIVEL_RIESGO",lambda s:(s=="Medio").mean()))
out["por_matriculas"]=mt.reset_index().assign(MATRICULAS_n=lambda x:x.MATRICULAS_n.astype(str)).to_dict("records")
alto=sc[sc.NIVEL_RIESGO=="Alto"]
out["senales_alto"]=alto.SENALES_RIESGO.str.split("; ").explode().str.replace(r"Rezago de \d+ semestres","Rezago de 2 o más semestres",regex=True).str.replace(r"Parciales en el cuarto inferior.*","Parciales en el cuarto inferior del grupo",regex=True).value_counts().to_dict()
out["perfil_alto"]={"n":int(len(alto)),"primera_mat":float((alto.MATRICULAS_n==1).mean()),"ti":float(alto.DOC_TI.mean()),"no_matric_prev":float(alto.NO_MATRIC_PREVIO.mean()),"blq_papa_prev":float(alto.BLQ_PAPA_PREV.mean()),"cancelo_prev":float(alto.CANCELO_PREVIO.mean()),"con_parcial":float(alto.CON_PARCIAL.mean()),"mediana_mat":float(alto.MATRICULAS_n.median()),"edad_med":float(alto.EDAD_n.median()),"nivelar_mat":float(alto.NODO_INICIO.str.contains("Matem|dos").mean())}
out["alto_por_antiguedad"]={k:{"n":int(len(x)),"alto":int((x.NIVEL_RIESGO=="Alto").sum()),"medio":int((x.NIVEL_RIESGO=="Medio").sum())} for k,x in [("primera",sc[sc.MATRICULAS_n==1]),("antiguos",sc[sc.MATRICULAS_n>1])]}
out["parciales_2026"]={"con_parcial":float(sc.CON_PARCIAL.mean()),"sin_insc":float(sc.SIN_INSC.mean()),"n_asig_prom":float(sc.N_ASIG.mean()),"subieron":int(((sc.NIVEL_BASE!="Alto")&(sc.NIVEL_RIESGO=="Alto")).sum()),"bajaron":int(((sc.NIVEL_BASE=="Alto")&(sc.NIVEL_RIESGO!="Alto")).sum()),"cambiaron":int((sc.NIVEL_BASE!=sc.NIVEL_RIESGO).sum())}
json.dump(out, open(f"{d}/score_out.json","w"), indent=1, default=float)
print(json.dumps(out["parciales_2026"]), out["perfil_alto"])
# ---------- EXCEL ----------
orig_cols = [c for c in pd.read_pickle(f"{d}/matricula.pkl").columns if c!="ARCHIVO"]
base = sc[orig_cols].copy()
base["VALOR_RIESGO_BASE"]=(sc.VALOR_RIESGO_BASE*100).round(1).values; base["VALOR_RIESGO"]=(sc.VALOR_RIESGO*100).round(1).values; base["NIVEL_RIESGO"]=sc.NIVEL_RIESGO.values
base["ASIGNATURAS_INSCRITAS"]=sc.N_ASIG.values; base["ASIGNATURAS_CON_PARCIAL"]=sc.N_ASIG_CAL.values; base["ASIG_PARCIAL_BAJO_GRUPO"]=sc.ASIG_BAJO_GRUPO.values
base["SENALES_RIESGO"]=sc.SENALES_RIESGO.values
base = base.sort_values(["FACULTAD","PROGRAMA_CURRICULAR","VALOR_RIESGO"], ascending=[True,True,False])
res = pd.DataFrame(out["niveles_2026"]).rename(columns={"NIVEL_RIESGO":"Nivel","n":"Estudiantes","esperados":"Bloqueos esperados","p_prom":"Riesgo promedio (%)","con_parcial":"% con parciales calificados"})
res["Bloqueos esperados"]=res["Bloqueos esperados"].round(0); res["Riesgo promedio (%)"]=(res["Riesgo promedio (%)"]*100).round(1); res["% con parciales calificados"]=(res["% con parciales calificados"]*100).round(1)
pp = pd.DataFrame(out["por_programa"]).rename(columns={"n":"Estudiantes","alto":"Alto","medio":"Medio","bajo":"Bajo","esperados":"Bloqueos esperados","con_parcial":"% con parciales","pct_alto":"% Alto","pct_medio":"% Medio","tasa_hist":"Tasa bloqueo 2025-2S y 2026-1S (%)"})
for c in ["% con parciales","% Alto","% Medio","Tasa bloqueo 2025-2S y 2026-1S (%)"]: pp[c]=(pp[c]*100).round(1)
pp["Bloqueos esperados"]=pp["Bloqueos esperados"].round(0)
# Pérdida histórica (2024-2S a 2025-2S): no cambia con la matrícula nueva; se toma de la versión anterior del Excel.
ANT = os.environ["SAT_EXCEL_ANTERIOR"]
a = pd.read_excel(ANT, sheet_name="Todas las asignaturas")[["COD_ASIGNATURA","ASIGNATURA","UAB","TIPOLOGIA","PERIODOS","ESTUDIANTES_2024_2S_A_2025_2S","PERDIERON","PCT_PERDIDA_HISTORICA","RANGO_HISTORICO","PCT_2024-2S","PCT_2025-1S","PCT_2025-2S"]]
a = a.rename(columns={"ESTUDIANTES_2024_2S_A_2025_2S":"ESTUDIANTES","PCT_PERDIDA_HISTORICA":"PCT_PERDIDA","RANGO_HISTORICO":"RANGO"}); a["COD_ASIGNATURA"]=a.COD_ASIGNATURA.astype(str)
# Avance 2026-2S: se recalcula con las notas parciales vigentes (cur_sc).
_cs = pd.read_pickle(f"{d}/cur_sc.pkl"); _cs["COD_ASIGNATURA"]=_cs.COD_ASIGNATURA.astype(str)
a2 = _cs.groupby("COD_ASIGNATURA").agg(ASIGNATURA=("ASIGNATURA","first"),UAB=("UAB","first"),TIPOLOGIA=("TIPOLOGIA","first"),INSCRITOS=("DOCUMENTO","nunique"),
    CON_PARCIAL=("PROM",lambda s:int(s.notna().sum())),BAJO3=("BAJO3",lambda s:int(s.sum()))).reset_index()
a2["PORC_CAL_PROM"]=a2.COD_ASIGNATURA.map(_cs[_cs.PROM.notna()].groupby("COD_ASIGNATURA").porc_g.mean()).round(1)
a2["PCT_CON_PARCIAL"]=(a2.CON_PARCIAL/a2.INSCRITOS*100).round(1); a2["PCT_BAJO_3"]=(a2.BAJO3/a2.CON_PARCIAL.where(a2.CON_PARCIAL>0)*100).round(1)
a2.to_pickle(f"{d}/asig_2026.pkl")
a = a.merge(a2[["COD_ASIGNATURA","INSCRITOS","CON_PARCIAL","PORC_CAL_PROM","PCT_BAJO_3"]].rename(columns={"INSCRITOS":"INSCRITOS_2026_2S","CON_PARCIAL":"CON_PARCIAL_2026_2S","PORC_CAL_PROM":"PORC_CALIFICADO_2026_2S","PCT_BAJO_3":"PCT_PARCIAL_BAJO_3_2026_2S"}), on="COD_ASIGNATURA", how="left")
a = a.rename(columns={"ESTUDIANTES":"ESTUDIANTES_2024_2S_A_2025_2S","PERDIERON":"PERDIERON","PCT_PERDIDA":"PCT_PERDIDA_HISTORICA","RANGO":"RANGO_HISTORICO"})
a.to_pickle(f"{d}/asignaturas_final.pkl")
hist40 = a[a.PCT_PERDIDA_HISTORICA>40].sort_values(["PCT_PERDIDA_HISTORICA","ESTUDIANTES_2024_2S_A_2025_2S"],ascending=[False,False])
av = a2[a2.CON_PARCIAL>=20].sort_values("PCT_BAJO_3",ascending=False); av=av[av.PCT_BAJO_3>40]
av["RANGO"]=np.select([av.PCT_BAJO_3>70,av.PCT_BAJO_3>50],["Más del 70%","Más del 50%"],"Más del 40%")
dic = pd.DataFrame([
 ("VALOR_RIESGO_BASE","Probabilidad (%) de pérdida de la calidad de estudiante por razones académicas (bloqueos 37 o 38) al cierre de 2026-2S, estimada con el reporte de matrícula y el histórico de bloqueos (modelo base, gradient boosting entrenado con 2023-2S a 2026-1S)."),
 ("VALOR_RIESGO","Probabilidad (%) ajustada con las notas parciales cargadas en 2026-2S al 29/10/2026 (posición del estudiante frente a su grupo, número de asignaturas). Es el valor que define el nivel."),
 ("NIVEL_RIESGO","Bajo: VALOR_RIESGO menor que 5%. Medio: de 5% a menos de 15%. Alto: 15% o más. Los cortes equivalen a una y tres veces la tasa histórica de bloqueo académico (4,5% a 5%)."),
 ("ASIGNATURAS_INSCRITAS","Asignaturas del estudiante en el reporte de notas parciales de 2026-2S."),
 ("ASIGNATURAS_CON_PARCIAL","Asignaturas con al menos un parcial calificado al 29/10/2026."),
 ("ASIG_PARCIAL_BAJO_GRUPO","Asignaturas en las que el promedio ponderado de los parciales calificados del estudiante está en el cuarto inferior de su grupo (hasta cuatro)."),
 ("SENALES_RIESGO","Señales de riesgo presentes, derivadas de matrícula, histórico de bloqueos y notas parciales, para orientar la intervención. No son la fórmula del modelo."),
 ("Fuente","DINARA, con información del SIA: RE_MAT_PST_PLN (2023-1S a 2026-2S), RE_EST_BLQ_ACR (corte 29/10/2026) y RE_ASI_EST_NOT_PAR (2024-2S, 2025-1S, 2025-2S y avance de 2026-2S). Solo pregrado, Sede Medellín."),
], columns=["Campo","Descripción"])
with pd.ExcelWriter(os.environ["SAT_EXCEL_SALIDA"], engine="openpyxl") as w:
    base.to_excel(w, sheet_name="Matricula 2026-2S", index=False)
    res.to_excel(w, sheet_name="Resumen niveles", index=False)
    pp.to_excel(w, sheet_name="Por programa", index=False)
    hist40.to_excel(w, sheet_name="Asig. perdida hist. >40%", index=False)
    av.to_excel(w, sheet_name="Asig. avance 2026-2S >40%", index=False)
    a.to_excel(w, sheet_name="Todas las asignaturas", index=False)
    dic.to_excel(w, sheet_name="Diccionario", index=False)
print("hist>40:", len(hist40), hist40.RANGO_HISTORICO.value_counts().to_dict(), " avance>40:", len(av), av.RANGO.value_counts().to_dict())
