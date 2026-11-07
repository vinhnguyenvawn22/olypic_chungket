import { useEffect, useRef, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Pin, PinOff, X } from 'lucide-react';

export default function FloatingPanel({title,side='right',narrow,guided=false,onClose,pinned,onPin,children,notification,className=''}:{title:string;guided?:boolean;side?:'left'|'right';narrow:boolean;onClose:()=>void;pinned?:boolean;onPin?:()=>void;children:ReactNode;notification?:ReactNode;className?:string}){
  const root=useRef<HTMLElement>(null);
  const close=useRef<HTMLButtonElement>(null);
  const closeAction=useRef(onClose);closeAction.current=onClose;
  useEffect(()=>{
    if(guided)return;
    const previous=document.activeElement as HTMLElement|null;
    close.current?.focus({preventScroll:true});
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!document.fullscreenElement&&root.current?.contains(document.activeElement)){event.preventDefault();event.stopPropagation();closeAction.current();}};
    root.current?.addEventListener('keydown',escape);
    const element=root.current;
    return()=>{element?.removeEventListener('keydown',escape);if(previous?.isConnected)previous.focus({preventScroll:true});};
  },[guided]);
  return <motion.aside ref={root} role={narrow&&!guided?'dialog':'region'} aria-modal={narrow&&!guided?true:undefined} aria-label={title} className={`floating-panel ${side} ${className}`} initial={narrow?{y:30,opacity:0}:{x:side==='left'?-20:20,opacity:0}} animate={{x:0,y:0,opacity:1}} exit={narrow?{y:30,opacity:0}:{x:side==='left'?-20:20,opacity:0}} transition={{duration:.22}} onKeyDown={event=>{
    if(!narrow||event.key!=='Tab')return;
    const items=root.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary,[tabindex="0"]');
    if(!items?.length)return;const first=items[0],last=items[items.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }}><div className="floating-panel-heading"><div><span className="eyebrow">CLASSROOM CONTROL</span><h2>{title}</h2></div><div>{onPin&&!narrow&&<button className={`icon-btn ${pinned?'selected':''}`} aria-label={pinned?'Bỏ ghim cảm biến':'Ghim cảm biến'} aria-pressed={pinned} onClick={onPin}>{pinned?<PinOff size={17}/>:<Pin size={17}/>}</button>}<button ref={close} className="icon-btn" aria-label={`Đóng ${title.toLowerCase()}`} onClick={onClose}><X size={20}/></button></div></div>{notification}{children}</motion.aside>;
}
