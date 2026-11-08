'use strict';
const field=id=>document.getElementById(id);
const sensors=['Temperature','Humidity','Light','CO2','HumidityRatio'];
let samples=[], truth=null, source='', result=null, version=0;
const fmt=x=>x===null||x===undefined?'—':Number(x).toLocaleString('vi-VN',{minimumFractionDigits:4,maximumFractionDigits:4});
function reset(){version++;samples=[];truth=null;result=null;source='';field('date').value='2015-01-01T08:00:00';field('reveal').checked=false;error('');render();}
function error(message){field('error').textContent=message;field('error').hidden=!message;}
async function api(url,options){const res=await fetch(url,options);const data=await res.json();if(!res.ok)throw new Error(data.error);return data;}
const post=(url,data)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
function render(){
 const last=result?.last;field('state').textContent=last?`Dự đoán · ${last.state}`:'Chưa có mẫu';
 field('action').textContent=last?(last.recommend?'Đề xuất kiểm tra phòng và thiết bị':last.prediction===null?'Kiểm tra dữ liệu đầu vào':'Tiếp tục theo dõi'):'Chờ dữ liệu cảm biến.';
 field('score').textContent=fmt(last?.score);field('run').textContent=last?`${last.streak} mẫu`:'—';field('why').textContent=last?.reason||'';
 field('threshold').textContent=last?`Ngưỡng phân lớp ${fmt(last.classification_threshold)}. Tích lũy khi điểm nhỏ hơn ${fmt(last.advisory_threshold)}.`:'';
 field('reveal').disabled=!truth||!result;const actual=truth?.at(-1);field('truth').textContent=field('reveal').checked&&actual!=null?`Nhãn thực tế ở mẫu cuối · ${actual===1?'Có người':'Trống'}`:'';
 field('source').textContent=samples.length?`${source} · ${samples.length} mẫu · hiển thị tối đa 12 mẫu cuối`:'Chưa có dữ liệu.';
 const body=field('body');body.replaceChildren();for(const row of result?.recent||[]){const tr=document.createElement('tr');for(const value of [row.sample,row.date,fmt(row.score),row.state,row.streak,row.recommend?'Kiểm tra':'Chờ']){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}
}
async function evaluate(){const token=++version;error('');if(!samples.length){result=null;render();return;}try{const answer=await post('/predict',{mode:field('model').value,rows:samples});if(token===version){result=answer;render();}}catch(e){if(token===version){result=null;render();error(e.message);}}}
function nextTime(){const value=samples.at(-1)?.date;if(!value)return;const date=new Date(String(value).replace(' ','T').replace(/Z$/,'')+'Z');if(Number.isFinite(date.valueOf()))field('date').value=new Date(date.valueOf()+60000).toISOString().slice(0,19);}
function setData(data,label){samples=data.rows;truth=data.truth;source=label;field('reveal').checked=false;nextTime();return evaluate();}
field('manual').onsubmit=e=>{e.preventDefault();const row={date:field('date').value};for(const key of sensors)row[key]=Number(field(key).value);samples.push(row);if(truth)truth.push(null);source='Chuỗi nhập tay';nextTime();evaluate();};
field('reset').onclick=reset;field('model').onchange=evaluate;field('reveal').onchange=render;
field('loadCase').onclick=async()=>{try{const pick=field('case');const label=pick.options[pick.selectedIndex].text;const data=await api('/example/'+pick.value);await setData(data,label);}catch(e){error(e.message);}};
field('upload').onchange=async()=>{const f=field('upload').files[0];if(!f)return;try{if(f.size>4500000)throw new Error('Chọn CSV dưới 4,5 MB.');const d=await post('/csv',{csv:await f.text()});await setData(d,'CSV · '+f.name+(d.rows.length&&!('date' in d.rows[0])?' · giả định cách nhau 60 giây':''));}catch(e){error(e.message);}finally{field('upload').value='';}};
reset();
