import pandas as pd, numpy as np, warnings, json, pickle; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
pd.set_option("display.width",250); pd.set_option("display.max_rows",300)
import os; d=os.environ["SAT_DATA"]
rng=np.random.RandomState(11)
key=["PERIODO","COD_ASIGNATURA","GRUP_ACTA","DOCUMENTO"]; gkey=["PERIODO","COD_ASIGNATURA","GRUP_ACTA"]
def prep(n):
    n=n[n.TIPO_NIVEL=="PREGRADO"].copy(); n["PORC"]=pd.to_numeric(n.PORCENTAJE,errors="coerce"); n["CAL"]=pd.to_numeric(n.CALIFICACION_P,errors="coerce"); n["PNUM"]=pd.to_numeric(n.CODIGO_PRUEBA,errors="coerce"); return n[n.ANULADA=="N"]
cur = prep(pd.read_pickle(f"{d}/notas_20262.pkl")); his = prep(pd.read_pickle(f"{d}/notas.pkl"))
def sc_table(n): return n[n.PORC==100].drop_duplicates(key)[key+["ASIGNATURA","UAB","TIPOLOGIA","CAL"]].rename(columns={"CAL":"FINAL"}).set_index(key)
def partial_feats(p):
    p=p.copy(); p["W"]=p.PORC*p.CAL
    g=p.groupby(key).agg(sum_w=("W","sum"), porc_g=("PORC","sum"), k=("CAL","size")); g["PROM"]=g.sum_w/g.porc_g; return g[["PROM","porc_g","k"]]
# ---- current ----
cur_sc = sc_table(cur); cp = cur[(cur.PORC<100)&(cur.PORC>0)&cur.CAL.notna()]
cur_sc = cur_sc.join(partial_feats(cp)); cur_sc["porc_g"]=cur_sc.porc_g.fillna(0); cur_sc["k"]=cur_sc.k.fillna(0)
# empirical distribution of graded partials per GROUP (modal k among its students)
_ag = set(pd.read_pickle(f"{d}/agregados_docs.pkl")) if os.path.exists(f"{d}/agregados_docs.pkl") else set()
_cs = cur_sc.reset_index(); gk = _cs[~_cs.DOCUMENTO.isin(_ag)].groupby(gkey).k.agg(lambda s: int(s.mode()[0])); emp = gk.values
print("2026 group k dist:", pd.Series(emp).value_counts(normalize=True).sort_index().round(3).to_dict())
# ---- historical simulation: sample k per group, take first k partials in P order ----
his_sc = sc_table(his)
hp = his[(his.PORC<100)&(his.PORC>0)].sort_values(key+["PNUM"]).copy()
hp["rank"]=hp.groupby(key).cumcount()+1
groups = his_sc.reset_index()[gkey].drop_duplicates(); groups["kcut"]=rng.choice(emp, size=len(groups))
hp = hp.merge(groups, on=gkey, how="left"); hp = hp[(hp["rank"]<=hp.kcut)&hp.CAL.notna()]
his_sc = his_sc.join(partial_feats(hp)); his_sc["porc_g"]=his_sc.porc_g.fillna(0); his_sc["k"]=his_sc.k.fillna(0)
print("share student-courses con parcial: hist", his_sc.PROM.notna().mean().round(3), " 2026", cur_sc.PROM.notna().mean().round(3))
# ---- relative-to-group features ----
def add_rel(sc):
    sc=sc.reset_index()
    g = sc[sc.PROM.notna()].groupby(gkey).PROM
    sc = sc.join(g.median().rename("G_MED"), on=gkey).join(g.quantile(0.25).rename("G_Q1"), on=gkey).join(g.size().rename("G_N"), on=gkey)
    sc["DESV"]=sc.PROM-sc.G_MED; sc["BAJO_Q1"]=np.where(sc.PROM.notna(), (sc.PROM<=sc.G_Q1).astype(float), np.nan)
    sc["BAJO3"]=np.where(sc.PROM.notna(), (sc.PROM<3).astype(float), np.nan)
    return sc
cur_sc=add_rel(cur_sc); his_sc=add_rel(his_sc)
def student_feats(sc):
    g = sc.groupby(["PERIODO","DOCUMENTO"]).agg(N_ASIG=("COD_ASIGNATURA","size"), N_ASIG_CAL=("PROM", lambda s: s.notna().sum()),
        PROM_PARCIAL=("PROM","mean"), MIN_PARCIAL=("PROM","min"), PCT_ASIG_BAJO3=("BAJO3","mean"), DESV_GRUPO=("DESV","mean"), MIN_DESV=("DESV","min"), PCT_ASIG_Q1=("BAJO_Q1","mean"), PORC_CAL_PROM=("porc_g","mean"))
    g["PCT_ASIG_CAL"]=g.N_ASIG_CAL/g.N_ASIG; return g.reset_index().rename(columns={"PERIODO":"PER"})
sf = pd.concat([student_feats(his_sc), student_feats(cur_sc)]); sf.to_pickle(f"{d}/notas_feats.pkl"); cur_sc.to_pickle(f"{d}/cur_sc.pkl"); his_sc.to_pickle(f"{d}/his_sc.pkl")
print(sf.groupby("PER")[["N_ASIG","N_ASIG_CAL","PROM_PARCIAL","PCT_ASIG_BAJO3","DESV_GRUPO","PCT_ASIG_Q1"]].mean().round(2))
# ---- merge with base dataset ----
df = pd.read_pickle(f"{d}/dataset.pkl")
df["EDAD_c"] = df.EDAD_n.clip(16,45); df["MATRICULAS_c"]=df.MATRICULAS_n.clip(1,20); df["PBM_c"]=df.PBM_n.fillna(df.PBM_n.median()); df["REZAGO_c"]=df.REZAGO.fillna(0).clip(0,10)
df["ESTRATO_g"]=df.ESTRATO.where(df.ESTRATO.isin(["1","2","3","4","5","6"]),"Otro")
nd=df.NODO_INICIO.str.strip(); df["NODO_g"]=np.select([nd.str.contains("dos asignaturas"), nd.str.contains("Matemáticas"), nd.str.contains("Lecto")],["Nivelar dos","Nivelar matemáticas","Nivelar lectoescritura"],"No nivela")
df["ACCESO_g"]=np.where(df.ACCESO.str.contains("TRASLADO"),"Traslado",np.where(df.ACCESO.str.contains("DOBLE"),"Doble titulación","Examen")); df["ETAPA_g"]=df.ETAPA_PEAMA.fillna("No aplica")
df["OPCION_GRA_b"]=(df.OPCION_GRA=="SI").astype(int); df["TRASLADADO_b"]=(df.TRASLADADO=="S").astype(int); df["EXTRANJERO_b"]=(df.EXTRANJERO=="S").astype(int)
df = df.merge(sf, on=["PER","DOCUMENTO"], how="left")
df["SIN_INSCRIPCION"]=df.N_ASIG.isna().astype(int)
num = ["MATRICULAS_c","EDAD_c","PBM_c","REZAGO_c","N_BLQ_PREV","INDICADOR_A3_n","INDICADOR_B2_n"]
bin_ = ["DOC_TI","PRIMERA_MATRICULA","NO_MATRIC_PREVIO","CANCELO_PREVIO","BLQ_PAPA_PREV","BLQ_CREDITOS_PREV","BLQ_ACAD_PER_ANTERIOR","BLQ_RESERVA_PER_ANTERIOR","RESERVA_PREV","TRASLADO_PREV","REINGRESO_TRASLADO","OPCION_GRA_b","TRASLADADO_b","RESIDE_FUERA_ANT","EXTRANJERO_b"]
cat = ["SEXO","ESTRATO_g","TIPCOLEGIO_g","PROGRAMA_ESPECIAL","ACCESO_g","ETAPA_g","NODO_g","PROGRAMA_CURRICULAR"]
NOT_ABS = ["N_ASIG","N_ASIG_CAL","PCT_ASIG_CAL","PROM_PARCIAL","MIN_PARCIAL","PCT_ASIG_BAJO3","SIN_INSCRIPCION"]
NOT_REL = ["N_ASIG","N_ASIG_CAL","PCT_ASIG_CAL","DESV_GRUPO","MIN_DESV","PCT_ASIG_Q1","SIN_INSCRIPCION"]
NOT_ALL = list(dict.fromkeys(NOT_ABS+NOT_REL))
def mk(nums):
    pre = ColumnTransformer([("num","passthrough",nums),("cat",OneHotEncoder(handle_unknown="ignore", min_frequency=30, sparse_output=False),cat)])
    return Pipeline([("pre",pre),("m",HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=60, l2_regularization=1.0, random_state=1))])
NP = ["2024-2S","2025-1S","2025-2S"]
tr = df[df.PER.isin(["2024-2S","2025-1S"])]; te = df[df.PER=="2025-2S"]; cur_df = df[df.PER=="2026-2S"]
out={}
for lab, nums in [("base", num+bin_), ("abs", num+bin_+NOT_ABS), ("rel", num+bin_+NOT_REL), ("all", num+bin_+NOT_ALL)]:
    g = mk(nums).fit(tr[nums+cat], tr.Y); p = g.predict_proba(te[nums+cat])[:,1]; pc = g.predict_proba(cur_df[nums+cat])[:,1]
    r = {"auc":roc_auc_score(te.Y,p),"ap":average_precision_score(te.Y,p),"brier":brier_score_loss(te.Y,p),"mean_te":float(p.mean()),"obs_te":float(te.Y.mean()),"mean_2026":float(pc.mean()),"alto_2026":float((pc>=0.15).mean())}
    m2 = te.N_ASIG_CAL.fillna(0)>0; r["auc_con_parcial"]=roc_auc_score(te.Y[m2],p[m2]); r["n_con_parcial"]=int(m2.sum())
    print(lab, {k:round(v,4) for k,v in r.items()}); out[lab]=r
json.dump(out, open(f"{d}/model_notas_cmp.json","w"), indent=1)
df.to_pickle(f"{d}/dataset_full.pkl")
