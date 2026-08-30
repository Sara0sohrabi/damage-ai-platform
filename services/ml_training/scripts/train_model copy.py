import os, json
from pathlib import Path
import joblib, pandas as pd
from sqlalchemy import create_engine, text
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DB=os.getenv("DATABASE_URL","postgresql+psycopg://damage:damage_dev@localhost:5432/damage_ai"); MODEL_DIR=Path(os.getenv("MODEL_DIR","/models")); MODEL_DIR.mkdir(parents=True,exist_ok=True)
DATASET_VERSION=os.getenv("DATASET_VERSION","dataset_001"); MODEL_VERSION=os.getenv("MODEL_VERSION","gboost_v3")
FEATURES=["coverage_code","event_type_code","province_code","city_code","loss_location_code","occupation_code","occupation_group_code","damaged_item_code","damage_type_code","financial_damage_type_code","property_type_code","structure_type_code","risk_density_code","ownership_type_code","premium","item_sum_insured","total_sum_insured","estimate_amount"]
TARGET="paid_loss"
engine=create_engine(DB)
df=pd.read_sql(text(f"SELECT {','.join(FEATURES)},{TARGET} FROM clean_damage_data WHERE dataset_version=:v AND paid_loss IS NOT NULL ORDER BY id"),engine,params={"v":DATASET_VERSION})
if len(df)<20: raise RuntimeError(f"Not enough clean rows: {len(df)}")
X,y=df[FEATURES].copy(),df[TARGET].astype(float)
cat=[c for c in FEATURES if c.endswith("_code")]; num=[c for c in FEATURES if c not in cat]
prep=ColumnTransformer([("cat",Pipeline([("imp",SimpleImputer(strategy="most_frequent")),("oh",OneHotEncoder(handle_unknown="ignore"))]),cat),("num",Pipeline([("imp",SimpleImputer(strategy="median")),("scale",StandardScaler())]),num)])
Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.20,random_state=42)
model=Pipeline([("preprocessor",prep),("regressor",GradientBoostingRegressor(random_state=42))]); model.fit(Xtr,ytr)
pred=model.predict(Xte)
# Clustering uses the same train-fitted preprocessor; no leakage from test.
train_matrix=model.named_steps["preprocessor"].transform(Xtr); test_matrix=model.named_steps["preprocessor"].transform(Xte)
cluster_count=min(5,max(2,len(Xtr)//50)); kmeans=KMeans(n_clusters=cluster_count,random_state=42,n_init=20).fit(train_matrix); test_clusters=kmeans.predict(test_matrix)
means=pd.Series(ytr.values).groupby(kmeans.labels_).mean().sort_values(); labels={}
for rank,cid in enumerate(means.index): labels[int(cid)]=(["very_low_loss","low_loss","medium_loss","high_loss","very_high_loss"] if cluster_count==5 else ["low_loss","medium_loss","high_loss"] if cluster_count==3 else ["low_loss","high_loss"] if cluster_count==2 else [f"band_{i+1}" for i in range(cluster_count)])[rank]
err=(yte.values-pred); denom=yte.abs().replace(0,pd.NA); ape=(pd.Series(abs(err),index=yte.index)/denom).dropna()
metrics={"rows":int(len(df)),"train_rows":int(len(Xtr)),"test_rows":int(len(Xte)),"mae":float(mean_absolute_error(yte,pred)),"rmse":float(mean_squared_error(yte,pred)**.5),"r2":float(r2_score(yte,pred)),"within_10pct":float((ape<=.10).mean()) if len(ape) else None,"within_20pct":float((ape<=.20).mean()) if len(ape) else None,"test_size":.20,"cluster_count":cluster_count}
artifact={"model":model,"kmeans":kmeans,"features":FEATURES,"target":TARGET,"metrics":metrics,"model_version":MODEL_VERSION,"dataset_version":DATASET_VERSION,"cluster_labels":labels,"cluster_train_mean_paid_loss":{int(k):float(v) for k,v in means.items()}}
path=MODEL_DIR/"damage_prediction.joblib"; joblib.dump(artifact,path)
with engine.begin() as conn:
    for table,col in [("test_prediction_results","model_version"),("cluster_results","model_version")]: conn.execute(text(f"DELETE FROM {table} WHERE {col}=:m"),{"m":MODEL_VERSION})
    conn.execute(text("DELETE FROM model_runs WHERE model_version=:m"),{"m":MODEL_VERSION})
    conn.execute(text("INSERT INTO model_runs(model_version,dataset_version,algorithm,test_size,train_rows,test_rows,mae,rmse,r2,within_10pct,within_20pct,cluster_count,status,artifact_path) VALUES (:m,:d,'GradientBoostingRegressor',:ts,:tr,:te,:mae,:rmse,:r2,:w10,:w20,:k,'completed',:p)"),{"m":MODEL_VERSION,"d":DATASET_VERSION,"ts":.2,"tr":len(Xtr),"te":len(Xte),"mae":metrics["mae"],"rmse":metrics["rmse"],"r2":metrics["r2"],"w10":metrics["within_10pct"],"w20":metrics["within_20pct"],"k":cluster_count,"p":str(path)})
    all_clusters=kmeans.predict(model.named_steps["preprocessor"].transform(X)); rows=[]
    for i,cid in enumerate(all_clusters): rows.append({"d":DATASET_VERSION,"m":MODEL_VERSION,"r":i,"c":int(cid),"cat":labels[int(cid)],"loss":float(y.iloc[i])})
    conn.execute(text("INSERT INTO cluster_results(dataset_version,model_version,source_row,cluster_id,category,paid_loss) VALUES (:d,:m,:r,:c,:cat,:loss)"),rows)
    test_positions=list(Xte.index); rows=[]
    for pos,actual,p,cid,est in zip(test_positions,yte,pred,test_clusters,Xte["estimate_amount"]): rows.append({"d":DATASET_VERSION,"m":MODEL_VERSION,"r":int(pos),"a":float(actual),"p":float(p),"e":float(abs(actual-p)),"ee":float(abs(actual-float(est))) if pd.notna(est) else None,"c":int(cid),"cat":labels[int(cid)],"est":None if pd.isna(est) else float(est)})
    conn.execute(text("INSERT INTO test_prediction_results(dataset_version,model_version,source_row,actual_paid_loss,predicted_paid_loss,estimate_amount,absolute_error,estimate_absolute_error,cluster_id,category) VALUES (:d,:m,:r,:a,:p,:est,:e,:ee,:c,:cat)"),rows)
print(json.dumps(metrics,ensure_ascii=False,indent=2)); print("Model saved:",path)
