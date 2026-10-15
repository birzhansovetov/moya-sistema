import {useEffect,useState} from 'react'
import {Button} from './ui'
export function Pronunciation({text,language}:{text:string;language:string}){
 const [voices,setVoices]=useState<SpeechSynthesisVoice[]>([]);const [error,setError]=useState('')
 useEffect(()=>{if(!('speechSynthesis' in window))return;const update=()=>setVoices(window.speechSynthesis.getVoices());update();window.speechSynthesis.addEventListener('voiceschanged',update);return()=>{window.speechSynthesis.removeEventListener('voiceschanged',update);window.speechSynthesis.cancel()}},[])
 const voice=voices.find(item=>item.lang.toLowerCase().split('-')[0]===language)
 function speak(){if(!voice)return;setError('');window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.lang=voice.lang;utterance.voice=voice;utterance.rate=.85;utterance.onerror=()=>setError('Не удалось произнести слово. Попробуйте ещё раз.');window.speechSynthesis.speak(utterance)}
 return <div><Button variant="quiet" disabled={!voice} onClick={speak}>Произнести слово</Button>{!voice?<p className="muted" role="status">На этом устройстве нет голоса для этого языка.</p>:<p className="muted">Синтетическое произношение устройства</p>}{error&&<p className="errorMessage" role="alert">{error}</p>}</div>
}
