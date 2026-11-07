import { Minus, Plus, UserRound, UsersRound } from 'lucide-react';
import { features, type Sensors } from './types';

type Props={staging:boolean;onMode:(value:boolean)=>void;count:number;onCount:(value:number)=>void;label:0|1|null;dirty:boolean;hasSnapshot:boolean;snapshot:Sensors|null;ready:boolean;busy:boolean;onScenario:(id:string)=>void;onCharacter:()=>void;csv:boolean;invalid:boolean};
export default function SceneStatus(p:Props){
  const state=p.label===null?'unknown':p.label===1?'occupied':'empty';
  return <div className="scene-experience">
    <div className="scene-mode-switch" role="group" aria-label="Chế độ nhân vật"><button aria-pressed={!p.staging} className={!p.staging?'active':''} onClick={()=>p.onMode(false)}><UserRound size={13}/> Minh họa kết quả AI</button><button aria-pressed={p.staging} className={p.staging?'active':''} onClick={()=>p.onMode(true)}><UsersRound size={13}/> Dàn dựng</button></div>
    {p.staging?<div className="staging-controls"><div className="staging-label">Cảnh dàn dựng — không phải kết quả AI</div><div className="actor-controls"><span>Nhân vật dàn dựng <b>{p.count}/6</b></span><button className="secondary" aria-label="Bớt nhân vật" disabled={p.count===0} onClick={()=>p.onCount(p.count-1)}><Minus size={13}/></button><button className="secondary" aria-label="Thêm nhân vật" disabled={p.count===6} onClick={()=>p.onCount(p.count+1)}><Plus size={13}/></button></div><p>Thêm người chỉ đổi cảnh. Cảm biến và nhận định AI được giữ độc lập.</p><div className="staging-scenarios"><button className="secondary" disabled={!p.ready||p.busy} onClick={()=>p.onScenario('occupied')}>Nạp chuỗi cảm biến có người</button><button className="secondary" disabled={!p.ready||p.busy} onClick={()=>p.onScenario('empty')}>Nạp chuỗi cảm biến phòng trống</button></div></div>:null}
    <div className={`actor-state ${state}`} data-state={state} data-scene-mode={p.staging?'staging':'ai'}><span className="actor-state-dot"/><span>{p.label===null?'Chưa có dự đoán':p.label===1?'AI dự đoán có người':'AI dự đoán phòng trống'}{p.dirty&&p.hasSnapshot?' · mẫu đã phân tích trước đó':''}</span><button className="text-btn" aria-label="Giải thích nhân vật" onClick={p.onCharacter}>Ý nghĩa nhân vật</button></div>
    <p className="character-disclaimer">Nhân vật minh họa trạng thái dự đoán; không thể hiện số người thực tế.</p>
    {p.invalid&&<p className="preview-warning">Mẫu không hợp lệ: cảnh ở trạng thái chưa xác định; hình ảnh cảm biến chỉ là nền minh họa.</p>}
    {p.dirty&&<div className="preview-warning" role="status">Thông số đã thay đổi — chưa phân tích lại. Ánh sáng đang xem trước; nhân vật giữ kết quả của mẫu trước.</div>}
    {p.snapshot&&<details className="snapshot-details"><summary>Thông số thực sự đã dùng cho kết quả {p.csv?'đang xem':'gần nhất'}</summary><div>{features.map(f=><span key={f.key}>{f.name}<b>{p.snapshot![f.key]} <small>{f.unit}</small></b></span>)}</div></details>}
    <p className="light-disclaimer">Ánh sáng minh họa độ rọi tại cảm biến; không xác định đèn đang bật/tắt hoặc mô phỏng vật lý chính xác.</p>
  </div>;
}
