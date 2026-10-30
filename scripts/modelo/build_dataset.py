import pandas as pd, numpy as np
pd.set_option("display.width",250); pd.set_option("display.max_rows",400)
import os; d=os.environ["SAT_DATA"]
mat = pd.read_pickle(f"{d}/matricula.pkl"); pre = mat[mat.TIPONIVEL=="PRE"].copy()
b = pd.read_pickle(f"{d}/bloqueos.pkl"); bp = b[b.NIVEL=="PREGRADO"].copy()
pre["PER"] = pre.PERIODO.str.replace("-01","-1S").str.replace("-02","-2S")
pre = pre.drop_duplicates(["PER","DOCUMENTO","PLAN"]).copy()
PERS = sorted(pre.PER.unique())
ACAD = ["37","38","7","8","9","10","14","100","110"]
bp["ACAD"] = bp.COD_BLOQUEO.isin(ACAD)
bp["FECHA"] = pd.to_datetime(bp.FECHA_BLOQUEO, format="%Y/%m/%d", errors="coerce")
# ---- target: academic block in period t (doc+plan) ----
ba = bp[bp.ACAD][["DOCUMENTO","COD_PLAN","PERIODO_BLOQUEO","COD_BLOQUEO"]].rename(columns={"COD_PLAN":"PLAN","PERIODO_BLOQUEO":"PER"})
tgt = ba.groupby(["PER","DOCUMENTO","PLAN"]).COD_BLOQUEO.agg(lambda s: ",".join(sorted(set(s)))).rename("COD_BLQ_ACAD").reset_index()
df = pre.merge(tgt, on=["PER","DOCUMENTO","PLAN"], how="left")
df["Y"] = df.COD_BLQ_ACAD.notna().astype(int)
# also check doc-only match to see plan mismatch
tgt_doc = ba.groupby(["PER","DOCUMENTO"]).size().rename("n").reset_index()
chk = pre.merge(tgt_doc, on=["PER","DOCUMENTO"], how="left")
print("match doc+plan:", df.Y.sum(), " match doc only:", chk.n.notna().sum())
# ---- numeric conversions ----
for c in ["EDAD","PBM","MATRICULAS","INDICADOR_A3","INDICADOR_B2","EXP","VALOR_FIN_MEN_662"]:
    df[c+"_n"] = pd.to_numeric(df[c], errors="coerce")
# ---- derived from matrícula ----
def per_index(p):  # 2023-1S -> 2023*2+0
    y,s = p.split("-"); return int(y)*2 + (0 if s.startswith("1") else 1)
df["PER_IDX"] = df.PER.map(per_index)
df["CONV_IDX"] = df.CONVOCATORIA.map(lambda p: per_index(p.replace("-01","-1S").replace("-03","-2S")))
df["APER_IDX"] = df.APERTURA.map(lambda p: per_index(p.replace("-01","-1S").replace("-03","-2S")))
df["SEM_DESDE_CONV"] = df.PER_IDX - df.CONV_IDX + 1        # semestres transcurridos desde la admisión
df["SEM_DESDE_APER"] = df.PER_IDX - df.APER_IDX + 1
df["REZAGO"] = df.SEM_DESDE_APER - df.MATRICULAS_n          # semestres no matriculados desde apertura
df["REINGRESO_TRASLADO"] = (df.APER_IDX > df.CONV_IDX).astype(int)
df["PRIMERA_MATRICULA"] = (df.MATRICULAS_n==1).astype(int)
df["CANCELO_ACTUAL"] = df.CANCELACION.notna().astype(int)
df["PROGRAMA_ESPECIAL"] = np.select([df.SUBACCESO.str.startswith("PEAMA"), df.SUBACCESO.str.startswith("PAES")|df.SUBACCESO.str.contains("VÍCTIMAS"), df.SUBACCESO.str.startswith("PAET")],["PEAMA","PAES","PAET"],"REGULAR")
df["ESTRATO_n"] = pd.to_numeric(df.ESTRATO, errors="coerce")
df["TIPCOLEGIO_g"] = df.TIPCOLEGIO.fillna("OTR").replace({"NOC":"OTR","IND":"OTR"})
df["DOC_TI"] = (df.T_DOCUMENTO=="TI").astype(int)
df["RESIDE_FUERA_ANT"] = (df.DEP_RESIDENCIA.fillna("")!="ANTIOQUIA").astype(int)
df["PROCEDE_FUERA_ANT"] = (df.DEP_PROCEDENCIA.fillna("")!="ANTIOQUIA").astype(int)
df["RESIDE_MEDELLIN"] = (df.MUN_RESIDENCIA.fillna("")=="MEDELLÍN").astype(int)
# ---- history from previous enrollment files (within window) ----
enr = pre[["PER","DOCUMENTO","PLAN","CANCELACION"]].copy(); enr["PER_IDX"]=enr.PER.map(per_index)
enr["CANC"]=enr.CANCELACION.notna().astype(int)
prev = enr[["PER_IDX","DOCUMENTO","PLAN","CANC"]].copy(); prev["PER_IDX"] += 1
prev = prev.rename(columns={"CANC":"CANCELO_PREVIO"}); prev["MATRIC_PREVIO"]=1
df = df.merge(prev, on=["PER_IDX","DOCUMENTO","PLAN"], how="left")
df["MATRIC_PREVIO"]=df.MATRIC_PREVIO.fillna(0).astype(int)
df["CANCELO_PREVIO"]=df.CANCELO_PREVIO.fillna(0).astype(int)
df["EN_VENTANA"] = (df.PER_IDX>per_index(PERS[0])).astype(int)  # whether previous period is observable
df["NO_MATRIC_PREVIO"] = ((df.MATRIC_PREVIO==0)&(df.EN_VENTANA==1)&(df.MATRICULAS_n>1)).astype(int)
df.loc[df.SEDE!="SEDE MEDELLÍN","NO_MATRIC_PREVIO"]=0   # matriculados por otra sede (PAET): su matrícula previa no está en estos archivos
# ---- history from block report: blocks with PERIODO_BLOQUEO < t (same doc, any plan) ----
bp["BPER_IDX"] = bp.PERIODO_BLOQUEO.str.extract(r"(\d{4}-[12])")[0].map(lambda p: per_index(p+"S") if isinstance(p,str) else np.nan)
hist_rows=[]
for t in PERS:
    ti = per_index(t)
    h = bp[bp.BPER_IDX < ti]
    g = h.groupby("DOCUMENTO").agg(
        N_BLQ_PREV=("COD_BLOQUEO","size"),
        N_BLQ_ACAD_PREV=("ACAD","sum"),
        BLQ_PAPA_PREV=("COD_BLOQUEO", lambda s: int((s=="37").any())),
        BLQ_CREDITOS_PREV=("COD_BLOQUEO", lambda s: int((s=="38").any())),
        RESERVA_PREV=("COD_BLOQUEO", lambda s: int(s.isin(["40","3"]).any())),
        RETIRO_NO_RENOVAR_PREV=("COD_BLOQUEO", lambda s: int(s.isin(["5","54"]).any())),
        TRASLADO_PREV=("COD_BLOQUEO", lambda s: int(s.isin(["2","42"]).any())),
        ULT_BLQ_IDX=("BPER_IDX","max"),
    ).reset_index()
    g["PER"]=t
    # academic block in the immediately previous period
    g["BLQ_ACAD_PER_ANTERIOR"] = h[h.ACAD & (h.BPER_IDX==ti-1)].groupby("DOCUMENTO").size().reindex(g.DOCUMENTO).notna().astype(int).values
    g["BLQ_RESERVA_PER_ANTERIOR"] = h[h.COD_BLOQUEO.isin(["40","3"]) & (h.BPER_IDX==ti-1)].groupby("DOCUMENTO").size().reindex(g.DOCUMENTO).notna().astype(int).values
    hist_rows.append(g)
hist = pd.concat(hist_rows)
df = df.merge(hist, on=["PER","DOCUMENTO"], how="left")
for c in ["N_BLQ_PREV","N_BLQ_ACAD_PREV","BLQ_PAPA_PREV","BLQ_CREDITOS_PREV","RESERVA_PREV","RETIRO_NO_RENOVAR_PREV","TRASLADO_PREV","BLQ_ACAD_PER_ANTERIOR","BLQ_RESERVA_PER_ANTERIOR"]:
    df[c]=df[c].fillna(0).astype(int)
df["SEM_DESDE_ULT_BLQ"] = (df.PER_IDX - df.ULT_BLQ_IDX).fillna(99)
df["ALGUN_BLQ_PREV"] = (df.N_BLQ_PREV>0).astype(int)
df.to_pickle(f"{d}/dataset.pkl")
print(df.shape)
print(df.groupby("PER").Y.agg(["size","sum","mean"]).round(4))
print(df[df.Y==1].COD_BLQ_ACAD.value_counts())
