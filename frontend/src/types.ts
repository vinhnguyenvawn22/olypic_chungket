export type ModelId = 'uneti15' | 'btc';
export const names: Record<ModelId, string> = {uneti15:'UNETI15 · LR cải tiến',btc:'BTC · Baseline'};
export const features = [
  {key:'Temperature',name:'Nhiệt độ',unit:'°C',min:10,max:40,step:.1,description:'Nhiệt độ không khí trong phòng.'},
  {key:'Humidity',name:'Độ ẩm',unit:'%',min:0,max:100,step:.1,description:'Độ ẩm tương đối của không khí.'},
  {key:'Light',name:'Ánh sáng',unit:'lux',min:0,max:1000,step:1,description:'Độ rọi đo tại vị trí cảm biến.'},
  {key:'CO2',name:'Nồng độ CO₂',unit:'ppm',min:0,max:2000,step:1,description:'Nồng độ CO₂; dùng làm đầu vào mô hình, không phải đánh giá an toàn.'},
  {key:'HumidityRatio',name:'Tỷ số ẩm',unit:'kg/kg',min:0,max:.02,step:.0001,description:'Khối lượng hơi nước trên khối lượng không khí khô.'},
] as const;
export type Feature = typeof features[number]['key'];
export type Sensors = Record<Feature,number>;
export type Sample = Sensors & {date:string};
export type Evidence={timestamp:string;probability:number};
export type Advisory={state:'no_data'|'invalid'|'monitoring'|'verifying'|'advisory'|'stale';code:string;title:string;summary:string;count:number;eligible:boolean;threshold:number;required_samples:number;max_gap_seconds:number;reset_reason:string|null;evidence:Evidence[];streak_started_at:string|null;episode_id:string|null};
export type DeviceId='lights'|'fan'|'screen';
export type Review={seen_at:string|null;room:'unknown'|'occupied'|'empty';checked_at:string|null;devices:Partial<Record<DeviceId,{state:'unknown'|'on'|'off';confirmed_at:string|null}>>};
export type EnergyStatus=Advisory&{source_mode:'manual'|'csv';sample_timestamp:string|null;server_time:string;expires_at:string|null;refresh_after_seconds:number|null;review:Review;device_actions:{id:DeviceId;name:string;state:'unknown'|'on'|'off';confirmed_at:string|null;message:string}[]};
export type Prediction = {model_id:ModelId; label:number; probability:number; count:number; alert:boolean; reset_reason:string|null;advisory?:Advisory;evidence?:Evidence[];streak_started_at?:string|null};
export type Row = {row:number; timestamp:string|null; sensors:Sensors|null; error:string|null; results:Partial<Record<ModelId,Prediction>>;advisory?:Advisory};
export type Context = Partial<Record<ModelId,{count:number;last_timestamp:string|null;evidence?:Evidence[];streak_started_at?:string|null;episode_id?:string|null}>>;
export type Response = {model_id:ModelId; rows:Row[]; context:Context; invalid_rows:number; assumed_timestamps?:boolean; source?:string};
export type ModelInfo = {id:ModelId;name:string;available:boolean;error:string|null;evaluation:Record<string,unknown>|null;parameters?:Record<string,unknown>};
export const defaults:Sensors={Temperature:23.18,Humidity:27.272,Light:426,CO2:721.25,HumidityRatio:.004792988};
export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response=await fetch(`/api${path}`,init);
  const body=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(typeof body?.detail==='string'?body.detail:response.status===422?'Dữ liệu hoặc thời gian không hợp lệ. Kiểm tra đủ 5 cảm biến.':`Không thể xử lý yêu cầu (${response.status}).`);
  return body;
}
export function exportRows(rows:Row[]) {
  const headers=['date',...features.map(f=>f.key),'model_id','label','probability','consecutive_samples','advisory','reset_reason','error'];
  const lines:unknown[][]=[headers];
  for(const row of rows){
    if(row.error) lines.push([row.timestamp,...features.map(f=>row.sensors?.[f.key]??''),'','','','','','',row.error]);
    else for(const result of Object.values(row.results)) if(result) lines.push([row.timestamp,...features.map(f=>row.sensors?.[f.key]??''),result.model_id,result.label,result.probability,result.count,result.alert,result.reset_reason??'','']);
  }
  const csv='\uFEFF'+lines.map(line=>line.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='uneti15-ket-qua.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
