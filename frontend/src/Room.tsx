import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { Billboard, ContactShadows, OrbitControls, PerformanceMonitor, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OrbitType } from 'three-stdlib';
import { features, type Feature, type Sensors } from './types';
import Student from './Student';

export type FocusTarget={key:Feature;nonce:number};
type Framing={left:number;right:number;top:number;bottom:number};
type Props={sensors:Sensors;intro:boolean;reduced:boolean;reset:number;alert:boolean;layer:Feature|null;onSelect:(key:Feature|'device'|'character')=>void;flat:boolean;label?:0|1|null;staging?:boolean;stageCount?:number;focus?:FocusTarget|null;framing?:Framing};
const sensorPositions:[number,number,number][]=[[-3.8,2,-2.7],[-3.8,2,.6],[1.1,3.15,-2],[2.55,1.9,-3.27],[-3.8,2,2.7]];
const seats:[number,number][]=[[-.5,.8],[1.5,-.7],[1.5,.8],[-2.5,-.7],[-2.5,.8],[-.5,2.3]];
function Label({text,width,height,background='#285851',color='#edf1d9'}:{text:string;width:number;height:number;background?:string;color?:string}){
  const texture=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=768;canvas.height=Math.round(768*height/width);
    const ctx=canvas.getContext('2d')!;ctx.fillStyle=background;ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle=color;ctx.textAlign='center';ctx.textBaseline='middle';
    const lines=text.split('\n');const spacing=canvas.height/(lines.length+1);ctx.font=`500 ${Math.min(40,spacing*.65)}px "Be Vietnam Pro", sans-serif`;
    lines.forEach((line,i)=>ctx.fillText(line,canvas.width/2,spacing*(i+1),canvas.width*.9));
    const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;return map;
  },[text,width,height,background,color]);
  useEffect(()=>()=>texture.dispose(),[texture]);
  return <mesh><planeGeometry args={[width,height]}/><meshBasicMaterial map={texture} toneMapped={false}/></mesh>;
}
function Box({p,s,c,r=0,rotation,onClick}:{p:[number,number,number];s:[number,number,number];c:string;r?:number;rotation?:[number,number,number];onClick?:(e:ThreeEvent<MouseEvent>)=>void}){
  if(r) return <RoundedBox args={s} radius={r} smoothness={2} position={p} rotation={rotation} castShadow receiveShadow onClick={onClick}><meshStandardMaterial color={c} roughness={.7}/></RoundedBox>;
  return <mesh position={p} rotation={rotation} castShadow receiveShadow onClick={onClick}><boxGeometry args={s}/><meshStandardMaterial color={c} roughness={.8}/></mesh>;
}
function Desk({x,z,teacher=false}:{x:number;z:number;teacher?:boolean}){
  return <group position={[x,0,z]}>
    <Box p={[0,.9,0]} s={[teacher?1.8:1.32,.12,.67]} c={teacher?'#c99058':'#e5bd83'} r={.045}/>
    {[-.49,.49].flatMap(lx=>[-.23,.23].map(lz=><Box key={`${lx}${lz}`} p={[lx,.46,lz]} s={[.055,.84,.055]} c="#557974"/>))}
    <Box p={[0,.53,.63]} s={[.54,.10,.5]} c="#6c9e93" r={.03}/>
    <Box p={[0,.89,.86]} s={[.53,.6,.07]} c="#82b1a4" r={.03}/>
    {[-.2,.2].flatMap(lx=>[.45,.81].map(lz=><Box key={`c${lx}${lz}`} p={[lx,.27,lz]} s={[.045,.5,.045]} c="#476e67"/>))}
    {!teacher&&<><Box p={[-.24,.98,-.05]} s={[.3,.035,.37]} c="#faf4dd" rotation={[0,.15,0]}/><Box p={[-.24,1.002,-.05]} s={[.03,.01,.3]} c="#d5ae6b"/><Box p={[.35,.98,.02]} s={[.21,.04,.3]} c="#b0cad2" rotation={[0,-.2,0]}/></>}
    {teacher&&<><Box p={[.2,1.03,0]} s={[.46,.12,.32]} c="#183c41" r={.02}/><Box p={[.2,1.24,-.13]} s={[.46,.34,.035]} c="#244f54" rotation={[-.15,0,0]}/></>}
  </group>;
}
function Fan({x,z,reduced,onSelect,alert}:{x:number;z:number;reduced:boolean;onSelect:()=>void;alert:boolean}){
  const rotor=useRef<THREE.Group>(null);
  useFrame((_,dt)=>{if(rotor.current&&!reduced) rotor.current.rotation.y+=dt*2.5;});
  return <group position={[x,3.25,z]} onClick={e=>{e.stopPropagation();onSelect();}}>
    <Box p={[0,.27,0]} s={[.045,.5,.045]} c="#d8cdb5"/>
    <mesh><cylinderGeometry args={[.12,.15,.15,16]}/><meshStandardMaterial color={alert?'#edba54':'#f5e9cd'} emissive={alert?'#a97416':'#000000'} emissiveIntensity={.25}/></mesh>
    <group ref={rotor}>{[0,1,2].map(i=><group key={i} rotation={[0,i*Math.PI*2/3,0]}><Box p={[.4,0,0]} s={[.78,.035,.15]} c="#dfceaa" r={.025}/></group>)}</group>
  </group>;
}
function Plant({p}:{p:[number,number,number]}){
  return <group position={p}><mesh position={[0,.24,0]} castShadow><cylinderGeometry args={[.24,.17,.45,12]}/><meshStandardMaterial color="#cb8d68"/></mesh>{[0,1,2,3,4].map(i=><mesh key={i} position={[Math.cos(i*1.6)*.14,.68+i*.09,Math.sin(i*1.6)*.14]} rotation={[.3,i,.4]} castShadow><sphereGeometry args={[.23,8,6]}/><meshStandardMaterial color={i%2?'#4d8a68':'#76a178'}/></mesh>)}</group>;
}
function Sensor({p,label,value,active,onClick}:{p:[number,number,number];label:string;value:string;active:boolean;onClick:()=>void}){
  const [hover,setHover]=useState(false);
  return <group position={p} onPointerOver={e=>{e.stopPropagation();setHover(true);}} onPointerOut={()=>setHover(false)} onClick={e=>{e.stopPropagation();onClick();}}>
    <mesh><sphereGeometry args={[hover?.13:.09,16,12]}/><meshStandardMaterial color={active?'#e9b863':'#bcf5c2'} emissive={active?'#d1a648':'#65d5a1'} emissiveIntensity={.6}/></mesh>
    <mesh rotation={[-Math.PI/2,0,0]}><torusGeometry args={[.17,.018,8,24]}/><meshBasicMaterial color="#69c4ab"/></mesh>
    {(hover||active)&&<Billboard position={[0,.47,0]}><Label text={`${label}\n${value}`} width={1.45} height={.57} background="#244d41"/></Billboard>}
  </group>;
}
function Camera({intro,reduced,reset,focus}:{intro:boolean;reduced:boolean;reset:number;focus:FocusTarget|null}){
  const controls=useRef<OrbitType>(null);
  const settled=useRef(false);
  const camera=useThree(state=>state.camera);
  const previousReset=useRef(reset);
  const desired=useRef(new THREE.Vector3(11,10,13));
  const lookAt=useRef(new THREE.Vector3(0,.7,0));
  useEffect(()=>{desired.current.set(...(intro?[11,10,13]:[9,8,11]) as [number,number,number]);lookAt.current.set(0,.7,0);settled.current=false;if(reset!==previousReset.current){camera.position.copy(desired.current);controls.current?.target.copy(lookAt.current);controls.current?.update();settled.current=true;previousReset.current=reset;}},[intro,reset,camera]);
  useEffect(()=>{if(!focus||intro)return;const index=features.findIndex(f=>f.key===focus.key);const p=sensorPositions[index];lookAt.current.set(p[0],p[1]-.25,p[2]);desired.current.set(p[0]+5.6,p[1]+3.2,p[2]+6.2);settled.current=false;},[focus,intro]);
  useFrame(({camera},dt)=>{if(!settled.current){const alpha=reduced?1:1-Math.exp(-dt*3);camera.position.lerp(desired.current,alpha);controls.current?.target.lerp(lookAt.current,alpha);controls.current?.update();if(camera.position.distanceTo(desired.current)<.025&&(!controls.current||controls.current.target.distanceTo(lookAt.current)<.025)) settled.current=true;}});
  return <OrbitControls ref={controls} makeDefault target={[0,.7,0]} enablePan={false} minDistance={5} maxDistance={19} minPolarAngle={.35} maxPolarAngle={1.35} autoRotate={intro&&!reduced} autoRotateSpeed={.35} onStart={()=>{settled.current=true;}}/>;
}
function Lighting({value,reduced}:{value:number;reduced:boolean}){
  const ambient=useRef<THREE.AmbientLight>(null),hemi=useRef<THREE.HemisphereLight>(null),sun=useRef<THREE.DirectionalLight>(null),bulb=useRef<THREE.PointLight>(null);
  useFrame((_,dt)=>{
    const amount=Math.sqrt(THREE.MathUtils.clamp(Number.isFinite(value)?value:0,0,1000)/1000);
    const update=(light:THREE.Light|null,target:number)=>{if(light)light.intensity=reduced?target:THREE.MathUtils.damp(light.intensity,target,5,Math.min(dt,.1));};
    update(ambient.current,.07+amount*.95);update(hemi.current,.10+amount*1.55);update(sun.current,.08+amount*3.3);update(bulb.current,amount*5.5);
  });
  return <><ambientLight ref={ambient} intensity={.3}/><hemisphereLight ref={hemi} args={['#fff6df','#839b8c',.4]}/><directionalLight ref={sun} position={[0,10,5]} intensity={1} castShadow shadow-mapSize={[1024,1024]} shadow-camera-left={-8} shadow-camera-right={8} shadow-camera-top={8} shadow-camera-bottom={-8} shadow-bias={-.001}/><pointLight ref={bulb} position={[0,3,0]} color="#ffe5a0" intensity={1}/></>;
}
function ViewportFraming({insets,reduced}:{insets:Framing|undefined;reduced:boolean}){
  const {camera,size}=useThree();
  const target=useRef({zoom:1,x:0,y:0});
  const current=useRef({zoom:1,x:0,y:0});
  useEffect(()=>{
    if(!insets){target.current={zoom:1,x:0,y:0};return;}
    const width=Math.max(180,size.width-insets.left-insets.right);
    const height=Math.max(140,size.height-insets.top-insets.bottom);
    target.current={zoom:.9*Math.min(1.25,width/(size.height*1.18),height/(size.height*.76)),x:(insets.right-insets.left)/2,y:(insets.bottom-insets.top)/2};
  },[insets?.left,insets?.right,insets?.top,insets?.bottom,size.width,size.height]);
  useFrame((_,dt)=>{
    if(!(camera instanceof THREE.PerspectiveCamera))return;
    const alpha=reduced?1:1-Math.exp(-Math.min(dt,.1)*12);
    current.current.zoom=THREE.MathUtils.lerp(current.current.zoom,target.current.zoom,alpha);
    current.current.x=THREE.MathUtils.lerp(current.current.x,target.current.x,alpha);
    current.current.y=THREE.MathUtils.lerp(current.current.y,target.current.y,alpha);
    if(insets){camera.zoom=current.current.zoom;camera.setViewOffset(size.width,size.height,current.current.x,current.current.y,size.width,size.height);}
  });
  return null;
}
function SensorDisplay({sensors}:{sensors:Sensors}){
  const temperature=Number.isFinite(sensors.Temperature)?sensors.Temperature:0;
  const level=THREE.MathUtils.clamp((temperature-10)/30,0,1);
  return <group position={[1.85,1.95,-3.3]}>
    <Box p={[0,0,0]} s={[.56,1.0,.12]} c="#e8e6d7" r={.04}/>
    <Box p={[-.16,.02,.075]} s={[.07,.67,.02]} c="#c1cbbf"/>
    <Box p={[-.16,-.31+level*.335,.09]} s={[.05,Math.max(.025,level*.67),.02]} c="#cd936b"/>
    <group position={[.06,.23,.08]}><Label text={`${temperature.toFixed(1)} °C`} width={.35} height={.18} background="#e8e6d7" color="#355747"/></group>
    <group position={[.045,-.02,.08]}><Label text={`RH ${sensors.Humidity.toFixed(1)}%`} width={.38} height={.18} background="#e8e6d7" color="#477c8b"/></group>
    <group position={[.045,-.28,.08]}><Label text={`CO₂ ${sensors.CO2.toFixed(0)}`} width={.4} height={.16} background="#e8e6d7" color="#537a55"/></group>
  </group>;
}
function Scene(props:Props){
  const {sensors,intro,reduced,reset,alert,layer,onSelect,label=null,staging=false,stageCount=0,focus=null}=props;
  const tint=layer==='Temperature'?new THREE.Color('#6bbbc9').lerp(new THREE.Color('#e5a16b'),THREE.MathUtils.clamp((sensors.Temperature-10)/30,0,1)):new THREE.Color(layer==='Humidity'||layer==='HumidityRatio'?'#77c7df':'#9de5ba');
  const rawOpacity=layer==='Humidity'?sensors.Humidity/100:layer==='HumidityRatio'?sensors.HumidityRatio/.02:layer==='CO2'?sensors.CO2/2000:.5;
  const opacity=.08+THREE.MathUtils.clamp(Number.isFinite(rawOpacity)?rawOpacity:0,0,1)*.2;
  return <>
    <Lighting value={sensors.Light} reduced={reduced}/>
    <group position={[0,-.25,0]}>
      <Box p={[0,-.16,0]} s={[8.6,.4,7.6]} c="#57796e" r={.14}/>
      <Box p={[0,.065,0]} s={[8.35,.1,7.35]} c="#e9ddc1"/>
      {Array.from({length:9},(_,i)=><Box key={i} p={[-3.8+i*.95,.121,0]} s={[.013,.005,7.2]} c="#d5c9ac"/>)}
      {Array.from({length:8},(_,i)=><Box key={i} p={[0,.122,-3.3+i*.94]} s={[8.2,.005,.013]} c="#d5c9ac"/>)}
      <Box p={[0,1.85,-3.6]} s={[8.4,3.5,.16]} c="#f0e9d7"/>
      <Box p={[-4.1,1.85,0]} s={[.16,3.5,7.2]} c="#e1e6d6"/>
      <Box p={[0,.35,-3.48]} s={[8.3,.38,.08]} c="#abc1ad"/>
      <Box p={[-3.99,.35,0]} s={[.08,.38,7.2]} c="#abc1ad"/>
      <Box p={[-.5,2.12,-3.46]} s={[4.1,1.65,.12]} c="#ad926c" r={.03}/>
      <Box p={[-.5,2.12,-3.37]} s={[3.88,1.43,.05]} c="#285851"/>
      <Box p={[-.5,1.35,-3.27]} s={[4,.05,.18]} c="#d9c69e"/>
      <group position={[-.5,2.12,-3.33]}><Label text={'UNETI · AI04\nSmall signals. Smarter spaces.\nTemperature · Light · CO₂'} width={3.8} height={1.35}/></group>
      {[0,1].map(i=><group key={i} position={[-3.98,2.15,-1.65+i*3.1]}>
        <Box p={[0,0,0]} s={[.08,1.8,2.3]} c="#bdab88"/>
        <Box p={[.06,0,0]} s={[.04,1.6,2.1]} c="#a7d1d3"/>
        <Box p={[.1,0,0]} s={[.04,1.65,.05]} c="#fdf5de"/>
        <Box p={[.1,0,0]} s={[.04,.05,2.15]} c="#fdf5de"/>
        <Box p={[.14,-.91,0]} s={[.32,.09,2.5]} c="#f4ecd7"/>
      </group>)}
      <Box p={[3.05,1.3,-3.45]} s={[1.05,2.35,.14]} c="#b68a60" r={.025}/>
      <Box p={[3.05,1.8,-3.35]} s={[.7,.95,.04]} c="#c4dcd3"/>
      <mesh position={[3.4,1.2,-3.28]}><sphereGeometry args={[.05,12,8]}/><meshStandardMaterial color="#f5d889"/></mesh>
      <Desk x={-.65} z={-2.3} teacher/>
      {[-2.5,-.5,1.5].flatMap(x=>[-.7,.8,2.3].map(z=><Desk key={`${x},${z}`} x={x} z={z}/>))}
      {seats.map((seat,i)=><Student key={i} seat={seat} index={i} staging={staging} present={!intro&&(staging?i<stageCount:i===0&&label===1)} unknown={intro||(!staging&&label===null)} reduced={reduced} onSelect={()=>onSelect('character')}/>)}
      <SensorDisplay sensors={sensors}/>
      <Plant p={[-3.5,.13,-3]}/><Plant p={[3.45,.13,2.9]}/>
      <Box p={[2.9,.68,2.8]} s={[.8,1.1,.6]} c="#d4b58a" r={.025}/>
      <Box p={[2.9,1.27,2.8]} s={[.86,.07,.65]} c="#f5e9cb"/>
      <Box p={[2.9,1.36,2.8]} s={[.55,.12,.32]} c="#86a8b2"/>
      <mesh position={[1.9,2.9,-3.46]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[.25,.25,.06,32]}/><meshStandardMaterial color="#f9f2dd"/></mesh>
      <Box p={[1.9,2.96,-3.4]} s={[.025,.14,.02]} c="#355c55" rotation={[0,0,-.3]}/>
      <Box p={[1.97,2.9,-3.4]} s={[.14,.025,.02]} c="#355c55"/>
      {[-1.9,1.9].map(x=><group key={x} position={[x,3.6,-.6]} onClick={e=>{e.stopPropagation();onSelect('device');}}>
        <Box p={[0,0,0]} s={[1.05,.09,.33]} c={alert?'#efbf63':'#e0d5ba'} r={.025}/><Box p={[0,-.055,0]} s={[.92,.025,.25]} c="#fff4c2"/>
      </group>)}
      <Fan x={-.5} z={1.35} reduced={reduced} alert={alert} onSelect={()=>onSelect('device')}/>
      {features.map((f,i)=><Sensor key={f.key} p={sensorPositions[i]} label={f.name} value={`${sensors[f.key].toFixed(f.key==='HumidityRatio'?5:1)} ${f.unit}`} active={layer===f.key||focus?.key===f.key} onClick={()=>onSelect(f.key)}/>)}
      {layer&&<mesh position={[0,.15,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[7.9,6.9]}/><meshBasicMaterial color={tint} transparent opacity={opacity} depthWrite={false}/></mesh>}
    </group>
    <ContactShadows position={[0,-.64,0]} opacity={.3} scale={18} blur={2.5} far={8} resolution={256}/>
    <Camera intro={intro} reduced={reduced} reset={reset} focus={focus}/>
    <ViewportFraming insets={props.framing} reduced={reduced}/>
  </>;
}
function FlatRoom({onSelect,sensors,label=null,staging=false,stageCount=0,intro}:Props){
  const count=intro?0:staging?stageCount:label===1?1:0;
  const brightness=.28+Math.sqrt(THREE.MathUtils.clamp(sensors.Light,0,1000)/1000)*.72;
  return <div className="flat-room"><div className="flat-environment" style={{filter:`brightness(${brightness})`}}><div className="flat-board">UNETI SMART CLASSROOM <small>Chế độ 2D · đủ chức năng phân tích</small></div><div className="flat-desks">{Array.from({length:9},(_,i)=><span key={i}><i/><i/>{i<count&&<button className="flat-person" aria-label="Nhân vật minh họa" onClick={()=>onSelect('character')}><span/><b/></button>}</span>)}</div></div><div className="flat-sensors">{features.map(f=><button key={f.key} onClick={()=>onSelect(f.key)}>{f.name}<b>{sensors[f.key]} <small>{f.unit}</small></b></button>)}</div></div>;
}
class RoomBoundary extends Component<{children:ReactNode;fallback:ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?this.props.fallback:this.props.children;}
}
function supportsWebGL(){try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'));}catch{return false;}}
export default function Room(props:Props){
  const [supported]=useState(supportsWebGL);
  const [quality,setQuality]=useState(window.innerWidth<700?1:Math.min(window.devicePixelRatio,1.6));
  const safeSensors=Object.fromEntries(features.map(f=>[f.key,Number.isFinite(props.sensors[f.key])?props.sensors[f.key]:0])) as Sensors;
  const safeProps={...props,sensors:safeSensors};
  const fallback=<FlatRoom {...safeProps}/>;
  if(!supported||props.flat) return fallback;
  return <RoomBoundary fallback={fallback}><Canvas shadows dpr={quality} camera={{position:[11,10,13],fov:36}} gl={{antialias:quality>1,alpha:true,powerPreference:'low-power'}} fallback={fallback}><PerformanceMonitor onDecline={()=>setQuality(1)}/><Suspense fallback={null}><Scene {...safeProps}/></Suspense></Canvas></RoomBoundary>;
}
