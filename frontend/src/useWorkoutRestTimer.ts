import {useCallback,useEffect,useState} from 'react'
function read(key:string):number|null{if(!key)return null;try{const value=Number(localStorage.getItem('moya-rest:'+key));if(Number.isFinite(value)&&value>Date.now())return value;localStorage.removeItem('moya-rest:'+key)}catch{/* optional local timer */}return null}
export function useWorkoutRestTimer(key:string){
 const [clock,setClock]=useState(()=>({key,until:read(key)}));const [now,setNow]=useState(Date.now)
 const until=clock.key===key?clock.until:null
 useEffect(()=>{setClock({key,until:read(key)});setNow(Date.now())},[key])
 const setRestUntil=useCallback((value:number|null)=>{if(key)try{if(value!==null)localStorage.setItem('moya-rest:'+key,String(value));else localStorage.removeItem('moya-rest:'+key)}catch{/* optional local timer */}setNow(Date.now());setClock({key,until:value})},[key])
 useEffect(()=>{if(until===null)return;const tick=()=>{setNow(Date.now());if(until<=Date.now())setRestUntil(null)};tick();const timer=window.setInterval(tick,1000);return()=>window.clearInterval(timer)},[until,setRestUntil])
 return {restUntil:until,setRestUntil,restRemaining:until===null?0:Math.max(0,Math.ceil((until-now)/1000))}
}
