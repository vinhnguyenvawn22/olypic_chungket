import argparse,json
from pathlib import Path
import joblib,pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,classification_report,confusion_matrix,f1_score,recall_score
FEATURES=['Temperature','Humidity','Light','CO2','HumidityRatio']

def load(p):
    df=pd.read_csv(p)
    missing=set(FEATURES+['Occupancy'])-set(df.columns)
    if missing: raise ValueError(f'Thieu cot: {missing}')
    return df

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--train',required=True,help='datatraining.txt');ap.add_argument('--val',required=True,help='datatest.txt');ap.add_argument('--out',default='outputs/AI04');a=ap.parse_args()
 tr,va=load(a.train),load(a.val);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(max_iter=1000,random_state=2026))
 model.fit(tr[FEATURES],tr.Occupancy);pred=model.predict(va[FEATURES])
 m={'accuracy':float(accuracy_score(va.Occupancy,pred)),'macro_f1':float(f1_score(va.Occupancy,pred,average='macro')),
    'false_empty_rate_among_occupied':float(((pred==0)&(va.Occupancy.to_numpy()==1)).sum()/max(1,(va.Occupancy==1).sum())),
    'recall_occupied':float(recall_score(va.Occupancy,pred,pos_label=1)),
    'classification_report':classification_report(va.Occupancy,pred,output_dict=True,zero_division=0),
    'confusion_matrix':confusion_matrix(va.Occupancy,pred,labels=[0,1]).tolist(),
    'features':FEATURES,'split':'official datatraining -> datatest; datatest2 reserved BTC'}
 joblib.dump(model,out/'model.joblib');(out/'metrics.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
 va[FEATURES].head(6).to_csv(out/'demo_sensors.csv',index=False)
 print('AI04 OK',round(m['macro_f1'],3),'false_empty_rate:',round(m['false_empty_rate_among_occupied'],3))
if __name__=='__main__':main()
