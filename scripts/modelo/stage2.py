import pandas as pd, numpy as np, warnings, json, pickle; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
pd.set_option("display.width",250); pd.set_option("display.max_rows",300)
import os; d=os.environ["SAT_DATA"]
df = pd.read_pickle(f"{d}/dataset_full.pkl"); M = pickle.load(open(f"{d}/models.pkl","rb")); feats=M["feats"]; num,bin_,cat=M["num"],M["bin"],M["cat"]
ALL = ["2023-2S","2024-1S","2024-2S","2025-1S","2025-2S","2026-1S"]; NP=["2024-2S","2025-1S","2025-2S"]
def mk():
    pre = ColumnTransformer([("num","passthrough",num+bin_),("cat",OneHotEncoder(handle_unknown="ignore", min_frequency=30, sparse_output=False),cat)])
    return Pipeline([("pre",pre),("m",HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=60, l2_regularization=1.0, random_state=1))])
# ---- cross-fitted base probability p1 for the notes periods ----
df["P1"]=np.nan
for t in NP:
    tr = df[df.PER.isin([p for p in ALL if p!=t])]; g = mk().fit(tr[feats], tr.Y)
    m = df.PER==t; df.loc[m,"P1"]=g.predict_proba(df.loc[m,feats])[:,1]
    print(t, "base cross-fit AUC", round(roc_auc_score(df.Y[m], df.P1[m]),4), "mean", round(df.P1[m].mean(),4), "obs", round(df.Y[m].mean(),4))
sc = pd.read_pickle(f"{d}/scored_2026_2S.pkl")[["DOCUMENTO","PLAN","VALOR_RIESGO"]]
m = df.PER=="2026-2S"; df.loc[m,"P1"] = df.loc[m,["DOCUMENTO","PLAN"]].merge(sc, on=["DOCUMENTO","PLAN"], how="left").VALOR_RIESGO.values
# ---- stage 2 features ----
df["LOGIT_P1"]=np.log(df.P1.clip(1e-4,1-1e-4)/(1-df.P1.clip(1e-4,1-1e-4)))
df["CON_PARCIAL"]=(df.N_ASIG_CAL.fillna(0)>0).astype(int)
for c in ["DESV_GRUPO","MIN_DESV","PCT_ASIG_Q1"]: df[c+"_f"]=df[c].fillna(0)
df["N_ASIG_f"]=df.N_ASIG.fillna(0); df["SIN_INSC"]=df.N_ASIG.isna().astype(int)
df["PCT_ASIG_CAL_f"]=df.PCT_ASIG_CAL.fillna(0)
S2 = ["LOGIT_P1","CON_PARCIAL","DESV_GRUPO_f","MIN_DESV_f","PCT_ASIG_Q1_f","N_ASIG_f","SIN_INSC","PCT_ASIG_CAL_f"]
def mk2_lr(): return Pipeline([("sc",StandardScaler()),("m",LogisticRegression(C=1.0,max_iter=2000))])
def mk2_gb(): return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=80, l2_regularization=1.0, random_state=1)
tr = df[df.PER.isin(["2024-2S","2025-1S"])]; te = df[df.PER=="2025-2S"]; cur = df[df.PER=="2026-2S"]
out={}
for lab, mk2 in [("lr",mk2_lr),("gb",mk2_gb)]:
    g = mk2().fit(tr[S2], tr.Y); p = g.predict_proba(te[S2])[:,1]; pc = g.predict_proba(cur[S2])[:,1]
    mp = te.CON_PARCIAL==1
    r={"auc":roc_auc_score(te.Y,p),"ap":average_precision_score(te.Y,p),"brier":brier_score_loss(te.Y,p),"mean_te":p.mean(),"obs_te":te.Y.mean(),"auc_con_parcial":roc_auc_score(te.Y[mp],p[mp]),"auc_base_con_parcial":roc_auc_score(te.Y[mp],te.P1[mp]),"auc_base":roc_auc_score(te.Y,te.P1),"mean_2026":pc.mean(),"alto_2026":(pc>=0.15).mean(),"medio_2026":((pc>=0.05)&(pc<0.15)).mean(),"mean_base_2026":cur.P1.mean()}
    print(lab, {k:round(float(v),4) for k,v in r.items()}); out[lab]=r
    if lab=="lr": print("  coef:", dict(zip(S2, g.named_steps["m"].coef_[0].round(3))))
# calibration of lr on test by bins
g = mk2_lr().fit(tr[S2], tr.Y); te=te.copy(); te["p"]=g.predict_proba(te[S2])[:,1]
bins=[0,0.01,0.02,0.03,0.05,0.075,0.10,0.15,0.20,0.30,0.50,1.0]
print(te.groupby(pd.cut(te.p,bins),observed=True).agg(n=("Y","size"),p=("p","mean"),obs=("Y","mean"),bloq=("Y","sum")).round(4))
def levels(p): return np.where(p>=0.15,"Alto",np.where(p>=0.05,"Medio","Bajo"))
for lab,pp in [("base",te.P1),("ajustado",te.p)]:
    t = te.assign(L=levels(pp)).groupby("L").agg(n=("Y","size"),obs=("Y","mean"),bloq=("Y","sum")); t["pct_est"]=t.n/t.n.sum(); t["pct_bloq"]=t.bloq/t.bloq.sum(); print(lab); print(t.round(3)); out[f"levels_{lab}"]=t.reset_index().to_dict("records")
# movement between levels in test
print(pd.crosstab(levels(te.P1), levels(te.p)))
json.dump(out, open(f"{d}/stage2_out.json","w"), indent=1, default=float)
df.to_pickle(f"{d}/dataset_full.pkl")
