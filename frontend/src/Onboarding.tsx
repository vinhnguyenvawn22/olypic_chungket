import { useLayoutEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Compass, X } from 'lucide-react';

export type GuideStep='welcome'|0|1|2|3;
type Rect={left:number;top:number;width:number;height:number};
type Props={step:GuideStep;csv:boolean;hasPrediction:boolean;validSample:boolean;onStep:(step:GuideStep)=>void;onClose:()=>void;onCopy:()=>void;onManual:()=>void};
const titles=['Nhập thông số cảm biến','Phân tích một mẫu','Đọc góc nhìn của AI','Kiểm tra khuyến nghị'];
const selectors=['.quick-field:first-child','.quick-footer > .primary','.ai-summary','.energy-badge'];

export default function Onboarding(p:Props){
  const root=useRef<HTMLDivElement>(null),card=useRef<HTMLElement>(null);
  const [rect,setRect]=useState<Rect|null>(null);
  const welcome=p.step==='welcome';
  // The guide is the only active dialog. Background controls remain visible for explanation.
  useLayoutEffect(()=>{
    const host=root.current?.parentElement;if(!host)return;
    const previous=document.activeElement as HTMLElement|null;
    const saved=new Map<HTMLElement,boolean>();
    const isolate=()=>Array.from(host.children).forEach(child=>{const node=child as HTMLElement;if(node!==root.current&&!saved.has(node)){saved.set(node,node.inert);node.inert=true;}});
    isolate();const observer=new MutationObserver(isolate);observer.observe(host,{childList:true});
    const focus=()=>card.current?.querySelector<HTMLButtonElement>('button')?.focus({preventScroll:true});
    focus();
    const guard=(event:FocusEvent)=>{if(!root.current?.contains(event.target as Node))focus();};
    document.addEventListener('focusin',guard);
    return()=>{observer.disconnect();document.removeEventListener('focusin',guard);saved.forEach((inert,node)=>node.inert=inert);requestAnimationFrame(()=>{if(previous?.isConnected&&!previous.closest('[inert]'))previous.focus({preventScroll:true});});};
  },[]);
  useLayoutEffect(()=>{
    const host=root.current?.parentElement;if(!host||!card.current)return;
    const observer=new ResizeObserver(()=>host.style.setProperty('--guide-height',`${Math.ceil(card.current!.getBoundingClientRect().height)}px`));
    observer.observe(card.current);return()=>{observer.disconnect();host.style.removeProperty('--guide-height');};
  },[]);
  useLayoutEffect(()=>{
    if(welcome){setRect(null);return;}
    const host=root.current?.parentElement;
    const target=host?.querySelector<HTMLElement>(selectors[p.step as number]);
    if(!target){setRect(null);return;}
    target.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});
    let frame=0;const start=performance.now();
    const measure=()=>{
      const box=target.getBoundingClientRect();
      let left=Math.max(8,box.left-5),top=Math.max(8,box.top-5),right=Math.min(innerWidth-8,box.right+5),bottom=Math.min(window.visualViewport?.height??innerHeight,box.bottom+5);
      let parent=target.parentElement;
      while(parent&&parent!==host){
        const style=getComputedStyle(parent),bounds=parent.getBoundingClientRect();
        if(/auto|scroll|hidden|clip/.test(style.overflowY)){top=Math.max(top,bounds.top);bottom=Math.min(bottom,bounds.bottom);}
        if(/auto|scroll|hidden|clip/.test(style.overflowX)){left=Math.max(left,bounds.left);right=Math.min(right,bounds.right);}
        parent=parent.parentElement;
      }
      const next={left,top,width:Math.max(0,right-left),height:Math.max(0,bottom-top)};
      setRect(old=>old&&Object.keys(next).every(key=>Math.abs(next[key as keyof Rect]-old[key as keyof Rect])<.5)?old:next);
    };
    const settle=()=>{measure();if(performance.now()-start<500)frame=requestAnimationFrame(settle);};
    const update=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(measure);};
    const observer=new ResizeObserver(update);observer.observe(target);if(host)observer.observe(host);if(card.current)observer.observe(card.current);
    window.addEventListener('resize',update);window.addEventListener('scroll',update,true);window.visualViewport?.addEventListener('resize',update);
    frame=requestAnimationFrame(settle);
    card.current?.querySelector<HTMLButtonElement>('.guide-next')?.focus({preventScroll:true});
    return()=>{cancelAnimationFrame(frame);observer.disconnect();window.removeEventListener('resize',update);window.removeEventListener('scroll',update,true);window.visualViewport?.removeEventListener('resize',update);};
  },[p.step,welcome,p.csv]);
  // Copy is deliberately contextual: a tour never changes a source or runs inference itself.
  return <div ref={root} className={`onboarding ${welcome?'guide-welcome':'guide-walkthrough'}`} onKeyDown={event=>{
    if(event.key==='Escape'){event.preventDefault();event.stopPropagation();p.onClose();}
    if(event.key==='Tab'){
      const buttons=card.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');if(!buttons?.length)return;
      const first=buttons[0],last=buttons[buttons.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  }}>
    <div className="guide-blocker"/>
    {!welcome&&rect&&rect.width>0&&rect.height>0?<div className="guide-spotlight" data-testid="guide-spotlight" style={rect}/>:<div className="guide-dim"/>}
    <section ref={card} className="guide-card" role="dialog" aria-modal="true" aria-labelledby="guide-title" aria-describedby="guide-description">
      <div className="guide-card-top"><span><Compass size={18}/>{welcome?'UNETI · BẮT ĐẦU TẠI ĐÂY':`HƯỚNG DẪN NHANH · ${Number(p.step)+1}/4`}</span><button className="icon-btn" aria-label="Đóng hướng dẫn" onClick={p.onClose}><X size={20}/></button></div>
      <h2 id="guide-title">{welcome?'Khám phá lớp học thông minh':titles[p.step as number]}</h2>
      <div id="guide-description" className="guide-description" aria-live="polite">
        {welcome?<p>Điều chỉnh thông số cảm biến, quan sát phòng học và xem AI hỗ trợ đánh giá trạng thái sử dụng phòng.</p>:p.step===0?<p>{p.csv?'Bạn đang phát lại CSV; các ô cảm biến chỉ để xem. Có thể sao chép mẫu sang phiên nhập tay mới bằng nút ở bước tiếp theo.':'Thanh cảm biến đã mở. Gõ trực tiếp nhiệt độ, độ ẩm, ánh sáng, CO₂ và tỷ số ẩm. Bạn có thể dùng dấu phẩy hoặc dấu chấm thập phân.'}</p>:p.step===1?<>{p.csv?<><p>CSV đã được phân tích bằng mô hình thật. Dùng thanh thời gian để xem từng mẫu. Nếu muốn chỉnh số liệu, hãy sao chép mẫu sang phiên nhập tay mới.</p><button className="secondary guide-copy" disabled={!p.validSample} onClick={p.onCopy}>Chuyển sang nhập tay với mẫu này</button>{!p.validSample&&<button className="text-btn" onClick={p.onManual}>Mở phiên nhập tay mới</button>}</>:<p>Thay đổi thông số sẽ cập nhật phần mô phỏng liên quan. Bấm <b>Phân tích mẫu</b> để cập nhật kết quả AI. Hướng dẫn này không tự gửi dữ liệu.</p>}</>:p.step===2?<p>Thẻ này hiển thị dự đoán và P(có người) của mô hình đang chọn. Mở “Góc nhìn của AI” để xem chi tiết và so sánh hai mô hình.{!p.hasPrediction&&' Hiện chưa có kết quả; hãy phân tích một mẫu sau khi kết thúc hướng dẫn.'}</p>:<p>Khuyến nghị phụ thuộc chuỗi kết quả AI và độ mới của dữ liệu. Mở thẻ để xem lý do, kiểm tra thực tế phòng và xác nhận thiết bị trước khi quyết định. AI không tự tắt điện.</p>}
      </div>
      {welcome?<div className="guide-welcome-actions"><button className="primary guide-next" onClick={()=>p.onStep(0)}>Hướng dẫn nhanh <ArrowRight size={18}/></button><button className="secondary" onClick={p.onClose}>Vào khám phá</button></div>:<><div className="guide-progress" aria-label={`Bước ${Number(p.step)+1} trên 4`}>{titles.map((title,i)=><span key={title} className={i<=Number(p.step)?'filled':''}/>)}</div><div className="guide-actions"><button className="text-btn" onClick={p.onClose}>Bỏ qua</button><div>{p.step!==0&&<button className="secondary" onClick={()=>p.onStep((Number(p.step)-1) as GuideStep)}><ArrowLeft size={16}/>Quay lại</button>}<button className="primary guide-next" onClick={()=>p.step===3?p.onClose():p.onStep((Number(p.step)+1) as GuideStep)}>{p.step===3?'Bắt đầu sử dụng':'Tiếp theo'}<ArrowRight size={16}/></button></div></div></>}
    </section>
  </div>;
}
