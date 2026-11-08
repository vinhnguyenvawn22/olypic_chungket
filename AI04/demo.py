import argparse,joblib,pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--model',default='outputs/AI04/model.joblib');ap.add_argument('--csv',default='outputs/AI04/demo_sensors.csv');a=ap.parse_args()
model=joblib.load(a.model);df=pd.read_csv(a.csv);p_occ=model.predict_proba(df)[:,list(model.classes_).index(1)]
count=0
for i,p in enumerate(p_occ,1):
 count=count+1 if p<.20 else 0
 action='GOI Y KIEM TRA DE TIET KIEM DIEN' if count>=3 else 'GIU NGUYEN/CHO XAC NHAN'
 print(f'Mau {i}: P(co nguoi)={p:.3f} | {action}')
print('Chi la GOI Y, khong tu dong tat dien. Khong dung du lieu thuc te phong hoc UNETI.')
