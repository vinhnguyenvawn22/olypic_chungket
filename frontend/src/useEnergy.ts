import { useEffect, useMemo, useState } from 'react';
import { api, type DeviceId, type EnergyStatus, type ModelId, type Review, type Row } from './types';

const EMPTY_REVIEW:Review={seen_at:null,room:'unknown',checked_at:null,devices:{}};
export function useEnergy(row:Row|undefined,model:ModelId,mode:'manual'|'csv',session:number,invalid:boolean){
  const [reviews,setReviews]=useState<Record<string,Review>>({});
  const prediction=row?.results[model];
  const reviewKey=`${session}:${model}:${prediction?.advisory?.episode_id??row?.timestamp??'no-data'}`;
  const review=reviews[reviewKey]??EMPTY_REVIEW;
  useEffect(()=>setReviews({}),[session]);
  const record=useMemo(()=>({mode,timestamp:row?.timestamp??null,invalid:invalid||!!row?.error,prediction:prediction?{model_id:model,probability:prediction.probability,count:prediction.count,reset_reason:prediction.reset_reason,evidence:prediction.evidence??[],streak_started_at:prediction.streak_started_at??null,episode_id:prediction.advisory?.episode_id??null}:null}),[row,model,mode,invalid,prediction]);
  const recordKey=JSON.stringify(record)+`:${session}`;
  const [result,setResult]=useState<{key:string;data?:EnergyStatus;expired:boolean;error?:string;loading:boolean}>({key:'',expired:false,loading:true});
  useEffect(()=>{
    let live=true,timer:ReturnType<typeof setTimeout>|undefined,controller:AbortController;
    async function refresh(expired=false){
      controller?.abort();controller=new AbortController();
      setResult(old=>({key:recordKey,data:old.key===recordKey&&!expired?old.data:undefined,expired,loading:true}));
      try{
        const data=await api<EnergyStatus>('/advisory/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...record,review}),signal:controller.signal});
        if(!live)return;
        setResult({key:recordKey,data,expired:data.state==='stale',loading:false});
        if(data.refresh_after_seconds!==null)timer=setTimeout(()=>void refresh(true),data.refresh_after_seconds*1000+30);
      }catch(error){if(live&&!(error instanceof DOMException&&error.name==='AbortError'))setResult({key:recordKey,expired,loading:false,error:error instanceof Error?error.message:'Không cập nhật được khuyến nghị.'});}
    }
    void refresh();
    return()=>{live=false;controller?.abort();if(timer)clearTimeout(timer);};
  },[recordKey,record,review]);
  function update(patch:Partial<Review>){setReviews(old=>({...old,[reviewKey]:{...(old[reviewKey]??EMPTY_REVIEW),...patch}}));}
  const current=result.key===recordKey?result:{key:recordKey,expired:false,loading:true};
  return {...current,review,
    markSeen:()=>update({seen_at:new Date().toISOString()}),
    verifyRoom:(room:Review['room'])=>update({room,checked_at:room==='unknown'?null:new Date().toISOString()}),
    setDevice:(id:DeviceId,state:'unknown'|'on'|'off')=>update({devices:{...review.devices,[id]:{state,confirmed_at:state==='unknown'?null:new Date().toISOString()}}}),
  };
}
export type EnergyController=ReturnType<typeof useEnergy>;
