import { useState } from 'react';
import { features, type Feature, type Sensors } from './types';

export type Drafts=Record<Feature,string>;
export type ParsedSensor={value:number;error:null}|{value:null;error:string};
export function parseSensor(key:Feature,raw:string):ParsedSensor{
  const text=raw.trim();
  if(!text)return {value:null,error:'Hãy nhập một giá trị.'};
  if(!/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$/.test(text))
    return {value:null,error:'Nhập số; dùng dấu phẩy hoặc dấu chấm thập phân.'};
  const value=Number(text.replace(',','.'));
  if(!Number.isFinite(value))return {value:null,error:'Giá trị phải là số hữu hạn.'};
  if(key==='Temperature'&&value< -273.15)return {value:null,error:'Nhiệt độ phải từ −273,15 °C trở lên.'};
  if(key!=='Temperature'&&value<0)return {value:null,error:'Giá trị không được âm.'};
  if(key==='Humidity'&&value>100)return {value:null,error:'Độ ẩm phải trong khoảng 0–100%.'};
  return {value,error:null};
}
const toDrafts=(values:Sensors)=>Object.fromEntries(features.map(f=>[f.key,String(values[f.key])])) as Drafts;

export function useSensorInput(initial:Sensors,onValues:(value:Sensors)=>void){
  const [drafts,setDrafts]=useState<Drafts>(()=>toDrafts(initial));
  const [touched,setTouched]=useState<Partial<Record<Feature,boolean>>>({});
  const parsed=Object.fromEntries(features.map(f=>[f.key,parseSensor(f.key,drafts[f.key])])) as Record<Feature,ParsedSensor>;
  const invalid=features.some(f=>parsed[f.key].error!==null);
  function edit(key:Feature,raw:string){
    setDrafts(old=>({...old,[key]:raw}));
    const result=parseSensor(key,raw);
    if(result.error===null)onValues({...initial,[key]:result.value});
  }
  function slide(key:Feature,value:number){
    setDrafts(old=>({...old,[key]:String(value)}));
    setTouched(old=>({...old,[key]:false}));
    onValues({...initial,[key]:value});
  }
  function validate():Sensors|null{
    const values={} as Sensors;
    setTouched(Object.fromEntries(features.map(f=>[f.key,true])));
    for(const f of features){const result=parsed[f.key];if(result.error!==null)return null;values[f.key]=result.value;}
    // Canonicalize decimal commas only on explicit confirmation, never while typing.
    setDrafts(toDrafts(values));onValues(values);return values;
  }
  function replace(values:Sensors){setDrafts(toDrafts(values));setTouched({});onValues({...values});}
  return {drafts,parsed,touched,invalid,edit,slide,validate,replace,touch:(key:Feature)=>setTouched(old=>({...old,[key]:true}))};
}
export type SensorEditor=ReturnType<typeof useSensorInput>;
