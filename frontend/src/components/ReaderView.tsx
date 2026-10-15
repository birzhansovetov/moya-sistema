import {useEffect,type ReactNode} from 'react'
import {Dialog,Button} from './ui'
import './ReaderView.css'
export function ReaderView({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
 useEffect(()=>{const previous=document.documentElement.dataset.reading;document.documentElement.dataset.reading='true';return()=>{if(previous)document.documentElement.dataset.reading=previous;else delete document.documentElement.dataset.reading}},[])
 return <Dialog open title={title} onClose={onClose} className="focusReader"><header className="focusReaderBar"><strong>{title}</strong><Button variant="quiet" onClick={onClose}>Закрыть чтение</Button></header><div className="focusReaderBody">{children}</div></Dialog>
}
