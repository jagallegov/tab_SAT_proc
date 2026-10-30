import pandas as pd, numpy as np, warnings, json, pickle; warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
pd.set_option("display.width",250); pd.set_option("display.max_rows",300)
import os; d=os.environ["SAT_DATA"]
df = pd.read_pickle(f"{d}/dataset.pkl")
df["EDAD_c"] = df.EDAD_n.clip(16,45); df["MATRICULAS_c"]=df.MATRICULAS_n.clip(1,20)
df["PBM_c"]=df.PBM_n.fillna(df.PBM_n.median()); df["REZAGO_c"]=df.REZAGO.fillna(0).clip(0,10)
df["ESTRATO_g"]=df.ESTRATO.where(df.ESTRATO.isin(["1","2","3","4","5","6"]),"Otro")
nd=df.NODO_INICIO.str.strip()
df["NODO_g"]=np.select([nd.str.contains("dos asignaturas"), nd.str.contains("Matemáticas"), nd.str.contains("Lecto")],["Nivelar dos","Nivelar matemáticas","Nivelar lectoescritura"],"No nivela")
df["ACCESO_g"]=np.where(df.ACCESO.str.contains("TRASLADO"),"Traslado",np.where(df.ACCESO.str.contains("DOBLE"),"Doble titulación","Examen"))
df["ETAPA_g"]=df.ETAPA_PEAMA.fillna("No aplica")
df["OPCION_GRA_b"]=(df.OPCION_GRA=="SI").astype(int); df["TRASLADADO_b"]=(df.TRASLADADO=="S").astype(int); df["EXTRANJERO_b"]=(df.EXTRANJERO=="S").astype(int)
num = ["MATRICULAS_c","EDAD_c","PBM_c","REZAGO_c","N_BLQ_PREV","INDICADOR_A3_n","INDICADOR_B2_n"]
bin_ = ["DOC_TI","PRIMERA_MATRICULA","NO_MATRIC_PREVIO","CANCELO_PREVIO","BLQ_PAPA_PREV","BLQ_CREDITOS_PREV","BLQ_ACAD_PER_ANTERIOR","BLQ_RESERVA_PER_ANTERIOR","RESERVA_PREV","TRASLADO_PREV","REINGRESO_TRASLADO","OPCION_GRA_b","TRASLADADO_b","RESIDE_FUERA_ANT","EXTRANJERO_b"]
cat = ["SEXO","ESTRATO_g","TIPCOLEGIO_g","PROGRAMA_ESPECIAL","ACCESO_g","ETAPA_g","NODO_g","PROGRAMA_CURRICULAR"]
feats = num+bin_+cat
tr_pers = ["2023-2S","2024-1S","2024-2S","2025-1S"]; va_pers=["2025-2S","2026-1S"]; all_pers = tr_pers+va_pers
def make_lr(C=0.3):
    pre = ColumnTransformer([("num",StandardScaler(),num+bin_),("cat",OneHotEncoder(handle_unknown="ignore", min_frequency=30),cat)])
    return Pipeline([("pre",pre),("m",LogisticRegression(C=C, max_iter=3000))])
def make_gb():
    pre = ColumnTransformer([("num","passthrough",num+bin_),("cat",OneHotEncoder(handle_unknown="ignore", min_frequency=30, sparse_output=False),cat)])
    return Pipeline([("pre",pre),("m",HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=60, l2_regularization=1.0, random_state=1))])
tr = df[df.PER.isin(tr_pers)]; va = df[df.PER.isin(va_pers)].copy()
out = {}
gb = make_gb().fit(tr[feats], tr.Y); va["p"] = gb.predict_proba(va[feats])[:,1]
lr = make_lr().fit(tr[feats], tr.Y); va["p_lr"] = lr.predict_proba(va[feats])[:,1]
out["metrics"] = {
 "gbm": {"auc":roc_auc_score(va.Y,va.p),"ap":average_precision_score(va.Y,va.p),"brier":brier_score_loss(va.Y,va.p)},
 "logit": {"auc":roc_auc_score(va.Y,va.p_lr),"ap":average_precision_score(va.Y,va.p_lr),"brier":brier_score_loss(va.Y,va.p_lr)},
 "n_train": int(len(tr)), "n_val": int(len(va)), "y_train": int(tr.Y.sum()), "y_val": int(va.Y.sum()), "rate_train": float(tr.Y.mean()), "rate_val": float(va.Y.mean())}
for per in va_pers:
    m=va.PER==per; out["metrics"][per]={"auc":roc_auc_score(va.Y[m],va.p[m]),"obs":float(va.Y[m].mean()),"pred":float(va.p[m].mean()),"n":int(m.sum()),"y":int(va.Y[m].sum())}
# calibration table GBM
bins=[0,0.01,0.02,0.03,0.05,0.075,0.10,0.15,0.20,0.30,0.50,1.0]
va["b"]=pd.cut(va.p,bins)
cal = va.groupby("b",observed=True).agg(n=("Y","size"),p=("p","mean"),obs=("Y","mean"),bloq=("Y","sum"))
print(cal.round(4)); out["calibration"]=cal.reset_index().assign(b=lambda x: x.b.astype(str)).to_dict("records")
# deciles
va["dec"]=pd.qcut(va.p,10,labels=False)+1
dec = va.groupby("dec").agg(n=("Y","size"),p=("p","mean"),obs=("Y","mean"),bloq=("Y","sum")); dec["pct_bloq"]=dec.bloq/dec.bloq.sum()
print(dec.round(4)); out["deciles"]=dec.reset_index().to_dict("records")
# ---- risk levels: cutoffs relative to base rate (validation): bajo < 1x base; medio 1x-3x; alto >= 3x ----
base = float(tr.Y.mean()); 
def levels(p, lo, hi): return np.where(p>=hi,"Alto",np.where(p>=lo,"Medio","Bajo"))
grid = {"base_train":base}
for lo,hi in [(0.05,0.15),(0.04,0.12),(0.05,0.20),(0.03,0.10),(0.05,0.10)]:
    L = levels(va.p,lo,hi); t = va.assign(L=L).groupby("L").agg(n=("Y","size"),obs=("Y","mean"),bloq=("Y","sum")); t["pct_est"]=t.n/t.n.sum(); t["pct_bloq"]=t.bloq/t.bloq.sum()
    print(f"\ncutoffs {lo},{hi}\n", t.round(3))
    grid[f"{lo}-{hi}"]=t.reset_index().to_dict("records")
out["level_grid"]=grid
# ---- permutation importance (GBM, validation), grouped by raw column ----
rng = np.random.RandomState(0); base_auc = roc_auc_score(va.Y, va.p); imp={}
for f in feats:
    s=0
    for r in range(3):
        X = va[feats].copy(); X[f]=rng.permutation(X[f].values); s += base_auc - roc_auc_score(va.Y, gb.predict_proba(X)[:,1])
    imp[f]=s/3
imp = pd.Series(imp).sort_values(ascending=False); print("\nPERMUTATION IMPORTANCE (AUC drop)\n", imp.round(4).to_string()); out["importance"]=imp.to_dict()
# ---- logit odds ratios (fit on all 6 periods) ----
lr_all = make_lr().fit(df[df.PER.isin(all_pers)][feats], df[df.PER.isin(all_pers)].Y)
names = lr_all.named_steps["pre"].get_feature_names_out(); coef = lr_all.named_steps["m"].coef_[0]
sc = lr_all.named_steps["pre"].named_transformers_["num"].scale_
ors = []
for i,(n_,c) in enumerate(zip(names,coef)):
    if n_.startswith("num__"):
        col=n_[5:]; ors.append((col, "por unidad" if col in num else "sí vs no", float(np.exp(c/sc[num.__add__(bin_).index(col)])), float(c)))
    else: ors.append((n_[5:], "vs referencia", float(np.exp(c)), float(c)))
ors = pd.DataFrame(ors, columns=["variable","tipo","OR","coef"]).sort_values("coef", ascending=False); print("\nODDS RATIOS\n", ors.round(3).to_string()); out["odds"]=ors.to_dict("records")
# ---- FINAL model on all periods, score 2026-2S ----
full = df[df.PER.isin(all_pers)]
gb_final = make_gb().fit(full[feats], full.Y)
sc_ = df[df.PER=="2026-2S"].copy(); sc_["VALOR_RIESGO"]=gb_final.predict_proba(sc_[feats])[:,1]
# in-sample (training) check of final model on last period for reference
print("\nfinal model mean p 2026-2S:", sc_.VALOR_RIESGO.mean().round(4), " expected blocks:", sc_.VALOR_RIESGO.sum().round(0))
sc_.to_pickle(f"{d}/scored_2026_2S.pkl"); va.to_pickle(f"{d}/validation_scored.pkl")
pickle.dump({"gb_final":gb_final,"gb_val":gb,"feats":feats,"num":num,"bin":bin_,"cat":cat}, open(f"{d}/models.pkl","wb"))
json.dump(out, open(f"{d}/model_out.json","w"), indent=1, default=float)
