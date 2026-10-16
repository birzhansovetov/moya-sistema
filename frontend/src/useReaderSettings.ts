import {useState} from 'react'
type Settings={theme:'light'|'sepia'|'dark';fontSize:number;lineHeight:number}
const defaults:Settings={theme:'light',fontSize:18,lineHeight:1.8}
export function useReaderSettings(){
 const [settings,setSettings]=useState<Settings>(()=>{try{const value=JSON.parse(localStorage.getItem('reader-settings')||'{}');return {theme:['light','sepia','dark'].includes(value.theme)?value.theme:'light',fontSize:[16,18,22,26].includes(value.fontSize)?value.fontSize:18,lineHeight:[1.5,1.8,2].includes(value.lineHeight)?value.lineHeight:1.8}}catch{return defaults}})
 function update(value:Partial<Settings>){setSettings(previous=>{const next={...previous,...value};try{localStorage.setItem('reader-settings',JSON.stringify(next))}catch{}return next})}
 return {settings,update}
}
