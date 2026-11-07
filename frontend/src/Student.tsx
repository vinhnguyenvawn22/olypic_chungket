import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

type Props = {
  present:boolean; unknown:boolean; staging:boolean; reduced:boolean;
  seat:[number,number]; index:number; onSelect:()=>void;
};

/** One representative actor in AI mode; independently placed actors in staging mode. */
export default function Student({present,unknown,staging,reduced,seat,index,onSelect}:Props){
  const root=useRef<THREE.Group>(null),body=useRef<THREE.Group>(null),head=useRef<THREE.Group>(null);
  const leftLeg=useRef<THREE.Group>(null),rightLeg=useRef<THREE.Group>(null);
  const leftArm=useRef<THREE.Group>(null),rightArm=useRef<THREE.Group>(null);
  const progress=useRef(0),fade=useRef(0),materials=useRef<THREE.MeshStandardMaterial[]>([]);
  const previousMode=useRef(staging);
  const path=useMemo(()=>new THREE.CatmullRomCurve3([
    new THREE.Vector3(3.05,.12,-3.05),new THREE.Vector3(3.05,.12,seat[1]+1.2),
    new THREE.Vector3(seat[0],.12,seat[1]+1.2),new THREE.Vector3(seat[0],.12,seat[1]+.63),
  ],false,'centripetal'),[seat[0],seat[1]]);
  const point=useMemo(()=>new THREE.Vector3(),[]),tangent=useMemo(()=>new THREE.Vector3(),[]);
  useEffect(()=>{
    const found:THREE.MeshStandardMaterial[]=[];
    root.current?.traverse(object=>{if(object instanceof THREE.Mesh){const mats=Array.isArray(object.material)?object.material:[object.material];for(const material of mats)if(material instanceof THREE.MeshStandardMaterial){material.transparent=true;found.push(material);}}});
    materials.current=found;
  },[]);
  useEffect(()=>{
    // A mode change cancels the previous actor path; invalid data removes stale actors immediately.
    if(previousMode.current!==staging||unknown){progress.current=0;fade.current=0;if(root.current)root.current.visible=false;}
    previousMode.current=staging;
  },[staging,unknown]);
  useFrame(({clock},delta)=>{
    if(!root.current||!body.current)return;
    const dt=Math.min(delta,.05),target=present&&!unknown?1:0;
    if(staging){progress.current=reduced?target:THREE.MathUtils.clamp(progress.current+(target?1:-1)*dt/.95,0,1);fade.current=THREE.MathUtils.smoothstep(progress.current,0,.12);}
    else {progress.current=target;fade.current=unknown?0:reduced?target:THREE.MathUtils.damp(fade.current,target,6,dt);}
    const opacity=fade.current;
    root.current.visible=opacity>.008;
    if(!root.current.visible)return;
    for(const material of materials.current){material.opacity=opacity;material.depthWrite=opacity>.95;}
    const t=staging?progress.current:1;
    const walk=staging&&t<.8;
    const seated=staging?THREE.MathUtils.smoothstep(t,.8,1):1;
    if(staging){path.getPoint(THREE.MathUtils.clamp(t/.82,0,1),point);root.current.position.copy(point);path.getTangent(Math.min(t/.82,.999),tangent);root.current.rotation.y=walk?Math.atan2(-tangent.x,-tangent.z):0;}
    else {root.current.position.set(seat[0],.12,seat[1]+.63);root.current.rotation.y=0;}
    const time=clock.elapsedTime+index*1.3;
    const breathe=reduced?0:Math.sin(time*1.7)*.008;
    body.current.position.y=THREE.MathUtils.lerp(.84,.62,seated)+breathe;
    body.current.rotation.x=seated*.08;
    if(head.current){head.current.rotation.x=seated*.12+(reduced?0:Math.sin(time*.55)*.035);head.current.rotation.y=reduced?0:Math.sin(time*.4)*.065;}
    const stride=walk&&!reduced?Math.sin(time*9)*.38:0;
    if(leftLeg.current)leftLeg.current.rotation.x=seated*Math.PI/2+stride;
    if(rightLeg.current)rightLeg.current.rotation.x=seated*Math.PI/2-stride;
    if(leftLeg.current?.children[1])leftLeg.current.children[1].rotation.x=-seated*Math.PI/2;
    if(rightLeg.current?.children[1])rightLeg.current.children[1].rotation.x=-seated*Math.PI/2;
    if(leftArm.current)leftArm.current.rotation.x=seated*.9-stride*.7;
    if(rightArm.current){rightArm.current.rotation.x=seated*1.02+stride*.7;rightArm.current.rotation.z=seated*(reduced?-.08:-.08+Math.sin(time*3)*.045);}
  });
  const skin=['#d8a47a','#bd8867','#ecc5a2'][index%3];
  const shirt=['#477c83','#c79758','#7c8e61','#a17c8f','#6686a4','#bd9074'][index%6];
  const part=(p:[number,number,number],s:[number,number,number],color:string)=><mesh position={p} castShadow><boxGeometry args={s}/><meshStandardMaterial color={color} roughness={.85}/></mesh>;
  return <group ref={root} visible={false} onClick={e=>{e.stopPropagation();onSelect();}}>
    <group ref={body}>
      {part([0,.2,0],[.34,.43,.24],shirt)}
      {part([0,-.035,0],[.32,.12,.25],'#344e5c')}
      <group ref={head} position={[0,.55,0]}>
        <mesh castShadow><sphereGeometry args={[.205,12,10]}/><meshStandardMaterial color={skin}/></mesh>
        <mesh position={[0,.075,.025]} castShadow><sphereGeometry args={[.208,12,8,0,Math.PI*2,0,Math.PI*.59]}/><meshStandardMaterial color="#3c3935"/></mesh>
        {part([0,-.01,-.19],[.055,.06,.04],skin)}
      </group>
      {[[-1,leftArm],[1,rightArm]].map(([side,ref])=><group key={side as number} ref={ref as typeof leftArm} position={[(side as number)*.23,.35,0]}>
        {part([0,-.11,0],[.12,.25,.13],shirt)}
        <group position={[0,-.24,0]} rotation={[.55,0,0]}>{part([0,-.095,0],[.09,.22,.09],skin)}{part([0,-.22,0],[.105,.07,.1],skin)}</group>
      </group>)}
      {[[-1,leftLeg],[1,rightLeg]].map(([side,ref])=><group key={side as number} ref={ref as typeof leftLeg} position={[(side as number)*.095,-.08,0]}>
        {part([0,-.16,0],[.14,.32,.14],'#344e5c')}
        <group position={[0,-.32,0]} rotation={[-Math.PI/2,0,0]}>{part([0,-.16,0],[.12,.32,.12],'#344e5c')}{part([0,-.34,-.04],[.15,.09,.24],'#e4e4d5')}</group>
      </group>)}
      <mesh position={[0,.37,.129]}><boxGeometry args={[.025,.1,.01]}/><meshStandardMaterial color="#e8e2bc"/></mesh>
    </group>
  </group>;
}
