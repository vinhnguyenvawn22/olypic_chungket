import { useEffect, useRef, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, ChevronUp, Copy, Droplets, Lightbulb, Settings2, Sparkles, Thermometer, Wind } from 'lucide-react';
import { features, type Feature, type Sensors } from './types';
import type { SensorEditor } from './sensorInput';

type Props={guided?:boolean;open:boolean;narrow:boolean;onOpen:()=>void;onClose:()=>void;editor:SensorEditor;values:Sensors;csv:boolean;validSample:boolean;active:Feature;onActive:(key:Feature)=>void;onAnalyze:()=>void;onCopy:()=>void;onManual:()=>void;ready:boolean;busy:boolean;dirty:boolean;onHeight:(height:number)=>void;notification?:ReactNode};
const icons=[Thermometer,Droplets,Lightbulb,Wind,Droplets];
export default function QuickSensorBar(p:Props){
  const root=useRef<HTMLElement>(null),previousFocus=useRef<HTMLElement|null>(null);
  const onHeight=useRef(p.onHeight);onHeight.current=p.onHeight;
  const onClose=useRef(p.onClose);onClose.current=p.onClose;
  useEffect(()=>{
    if(!root.current)return;
    const observer=new ResizeObserver(entries=>onHeight.current(Math.ceil(entries[0].contentRect.height)));
    observer.observe(root.current);return()=>observer.disconnect();
  },[]);
  useEffect(()=>{
    if(!p.open||p.guided)return;previousFocus.current=document.activeElement as HTMLElement|null;
    const frame=requestAnimationFrame(()=>{
      if(root.current?.contains(document.activeElement)&&document.activeElement instanceof HTMLInputElement)return;
      const input=root.current?.querySelector<HTMLInputElement>(`#${p.active}`);
      if(!p.csv){input?.focus({preventScroll:true});input?.select();}
      else root.current?.querySelector<HTMLButtonElement>('.quick-heading button')?.focus({preventScroll:true});
    });
    return()=>{cancelAnimationFrame(frame);if(previousFocus.current?.isConnected)previousFocus.current.focus({preventScroll:true});};
  },[p.open,p.guided]);
  useEffect(()=>{
    const content=root.current?.querySelector('.quick-content');if(!p.open||!content)return;
    let frame=0;
    const observer=new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>root.current?.querySelector<HTMLInputElement>('input[type="text"]:focus')?.scrollIntoView({block:'nearest',inline:'nearest'}));});
    observer.observe(content);return()=>{observer.disconnect();cancelAnimationFrame(frame);};
  },[p.open]);
  const summary=features.map(f=>({f,text:p.csv?(p.validSample?String(p.values[f.key]):'—'):p.editor.parsed[f.key].error===null?String(p.editor.parsed[f.key].value):'…'}));
  return <section ref={root} className={`quick-sensors ${p.open?'expanded sensor-drawer':'collapsed'} ${p.csv?'csv-readonly':''}`} role={p.open&&p.narrow&&!p.guided?'dialog':'region'} aria-modal={p.open&&p.narrow&&!p.guided?true:undefined} aria-label="Thông số cảm biến" onKeyDown={event=>{
    if(event.key==='Escape'&&p.open&&!document.fullscreenElement){event.preventDefault();event.stopPropagation();onClose.current();return;}
    if(!p.open||!p.narrow||event.key!=='Tab')return;
    const items=root.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),summary');if(!items?.length)return;
    const first=items[0],last=items[items.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }}>
    {!p.open?<button type="button" className="quick-summary" aria-label="Mở thông số cảm biến" aria-expanded={false} onClick={p.onOpen}><span className="quick-summary-label"><Settings2 size={16}/><span>Thông số cảm biến<small>{p.csv?'Dữ liệu phát lại':'Mở nhập nhanh'}</small></span></span><span className="quick-summary-values">{summary.map(({f,text})=><span key={f.key} title={`${f.name}: ${text} ${f.unit}`}><b>{text.replace('.',',')}</b><small>{f.unit}</small></span>)}</span><ChevronUp size={17}/></button>:<>
    <div className="quick-heading"><div><Settings2 size={17}/><h2>Thông số cảm biến</h2><span>{p.csv?'Dữ liệu phát lại':'Nhập nhanh'}</span></div><button type="button" className="icon-btn" aria-label="Thu gọn cảm biến" onClick={p.onClose}><ChevronDown size={20}/></button></div>
    {p.notification}
    <AnimatePresence initial={false}><motion.div className="quick-content" initial={{opacity:0}} animate={{opacity:1}} transition={{duration:.18}}>
      <form id="quick-sensor-form" noValidate onSubmit={event=>{event.preventDefault();if(!p.csv)p.onAnalyze();}} onKeyDown={event=>{if(event.key==='Enter'&&(event.repeat||event.nativeEvent.isComposing))event.preventDefault();}}>
      <div className="quick-fields">{features.map((f,i)=>{
        const Icon=icons[i],result=p.editor.parsed[f.key];
        const error=!p.csv&&p.editor.touched[f.key]?result.error:null;
        const value=p.csv?(p.validSample?String(p.values[f.key]):''):p.editor.drafts[f.key];
        return <div className={`quick-field ${p.active===f.key?'focused':''} ${error?'has-error':''}`} key={f.key}>
          <label htmlFor={f.key}><Icon size={15}/>{f.name}<small>{f.unit}</small></label>
          <input id={f.key} type="text" inputMode="decimal" autoComplete="off" spellCheck={false} aria-label={f.name} aria-invalid={!!error} aria-describedby={error?`${f.key}-error`:undefined} readOnly={p.csv} value={value} onFocus={event=>{p.onActive(f.key);event.currentTarget.parentElement?.scrollIntoView({block:'nearest',inline:'nearest'});if(!p.csv)event.currentTarget.select();}} onChange={event=>p.editor.edit(f.key,event.target.value)} onBlur={()=>p.editor.touch(f.key)}/>
          <input type="range" aria-label={`Điều chỉnh ${f.name}`} min={f.min} max={f.max} step={f.step} disabled={p.csv} value={Math.min(f.max,Math.max(f.min,p.values[f.key]))} onChange={event=>{p.onActive(f.key);p.editor.slide(f.key,Number(event.target.value));}}/>
          <div id={`${f.key}-error`} className="quick-field-error" aria-live="polite">{error??''}</div>
        </div>;
      })}</div>
      </form>
    </motion.div></AnimatePresence>
    <div className="quick-footer"><div>{p.csv?<><strong>Dữ liệu phát lại · chỉ xem</strong><span>{p.validSample?'Sao chép mẫu để chỉnh và phân tích trong phiên nhập tay mới.':'Mẫu hiện tại không hợp lệ; không thể sao chép.'}</span><button type="button" className="text-btn" onClick={event=>{event.preventDefault();p.onManual();}}>Nhập tay mới</button></>:<><strong>{p.editor.invalid?'Đang nhập số — giữ giá trị xem trước hợp lệ gần nhất':p.dirty?'Đã chỉnh thông số — chưa phân tích lại':'Sẵn sàng nhập và quan sát phòng'}</strong><details className="input-details"><summary>Chi tiết nhập liệu</summary><span>{features.find(f=>f.key===p.active)?.description} Slider là khoảng minh họa; có thể nhập số ngoài khoảng.</span></details></>}</div>{p.csv?<button key="copy-sample" type="button" className="primary" disabled={!p.validSample||p.busy} onClick={event=>{event.preventDefault();p.onCopy();}}><Copy size={16}/>Dùng mẫu này để nhập tay</button>:<button key="analyze-sample" className="primary predict-btn" type="submit" form="quick-sensor-form" disabled={!p.ready||p.busy}><Sparkles size={17}/>{p.busy?'Đang phân tích…':'Phân tích mẫu'}</button>}</div>
    </>}
  </section>;
}
