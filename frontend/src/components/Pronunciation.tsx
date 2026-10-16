import {useEffect,useState} from 'react'
import {Button} from './ui'
export function Pronunciation({text,language,label='Произнести слово'}:{text:string;language:string;label?:string}){
 const [playing,setPlaying]=useState(false)
 const [voices,setVoices]=useState<SpeechSynthesisVoice[]>([]);const [error,setError]=useState('')
 useEffect(()=>{if(!('speechSynthesis' in window))return;const update=()=>setVoices(window.speechSynthesis.getVoices());update();window.speechSynthesis.addEventListener('voiceschanged',update);return()=>{window.speechSynthesis.removeEventListener('voiceschanged',update);window.speechSynthesis.cancel()}},[])
 const voice=voices.find(item=>item.lang.toLowerCase().split('-')[0]===language)
 function speak(){if(!voice)return;setError('');window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.lang=voice.lang;utterance.voice=voice;utterance.rate=.85;utterance.onend=()=>setPlaying(false);utterance.onerror=event=>{setPlaying(false);if(event.error!=='canceled'&&event.error!=='interrupted')setError('Не удалось воспроизвести текст. Попробуйте ещё раз.')};setPlaying(true);window.speechSynthesis.speak(utterance)}
 return <div><Button variant="quiet" disabled={!voice} onClick={speak}>{label}</Button>{playing&&<Button variant="secondary" onClick={()=>{window.speechSynthesis.cancel();setPlaying(false)}}>Остановить</Button>}{!voice?<p className="muted" role="status">На этом устройстве нет голоса для этого языка.</p>:<p className="muted">Синтетическая озвучка устройства</p>}{error&&<p className="errorMessage" role="alert">{error}</p>}</div>
}
