export const GUIDE_KEY = 'uneti-onboarding-v2';
export const PRESENTATION_KEY = 'uneti-presentation-v1';

export function readPreference(key:string){
  try{return localStorage.getItem(key);}catch{return null;}
}
export function savePreference(key:string,value:string){
  try{localStorage.setItem(key,value);}catch{/* Preferences are optional when storage is blocked. */}
}
