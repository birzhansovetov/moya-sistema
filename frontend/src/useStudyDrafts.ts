import {useState} from 'react'
import {useQueryClient} from '@tanstack/react-query'
import {api,json} from './api'
import type {Attempt,Lesson,StudyPlan} from './studyTypes'
export type StudyDraft={plan_id:string;lesson_id:string;course_id:string;answers:string[];evidence:string;self_checks:boolean[];date:string;portfolio_url:string;create_key:string;revision:number|null;saved:boolean;draftPending:boolean;draftError:string;pending:boolean;error:string;result?:Attempt}
export type StoredStudyDraft={id:string;plan_id:string;lesson_id:string;revision:number;updated_at:string;content:Pick<StudyDraft,'answers'|'evidence'|'self_checks'|'date'|'portfolio_url'|'create_key'>}
export function newStudyDraft(plan:StudyPlan,lesson:Lesson,date:string):StudyDraft{return {plan_id:plan.id,lesson_id:lesson.id,course_id:plan.course_id,answers:lesson.quiz.map(()=>''),evidence:'',self_checks:lesson.rubric.map(()=>false),date,portfolio_url:'',create_key:crypto.randomUUID(),revision:null,saved:false,draftPending:false,draftError:'',pending:false,error:''}}
export function useStudyDrafts(onSaved:()=>void,userId:string|undefined){
 const client=useQueryClient()
 const [values,setValues]=useState<Record<string,StudyDraft>>({})
 function hydrate(items:StoredStudyDraft[],courseId:string){setValues(current=>{let changed=false;const next={...current};const remote=new Set(items.map(item=>item.plan_id+':'+item.lesson_id));for(const item of items){const key=item.plan_id+':'+item.lesson_id;const local=current[key];if(local&&(!local.saved||local.pending||local.draftPending||local.result||item.revision<=(local.revision??0)))continue;next[key]={...item.content,plan_id:item.plan_id,lesson_id:item.lesson_id,course_id:courseId,revision:item.revision,saved:true,draftPending:false,draftError:'',pending:false,error:''};changed=true}for(const [key,local] of Object.entries(current)){if(local.course_id===courseId&&local.saved&&!local.pending&&!local.draftPending&&!local.result&&!remote.has(key)){next[key]={...local,revision:null,saved:false,draftError:'Черновик удалён в другом окне. Текст остался здесь; сохраните снова.'};changed=true}}return changed?next:current})}
 function update(key:string,draft:StudyDraft,changes:Partial<StudyDraft>){setValues(current=>({...current,[key]:{...draft,...changes,create_key:crypto.randomUUID(),saved:false,draftError:'',error:'',result:undefined}}))}
 async function saveDraft(key:string,draft:StudyDraft){
  if(draft.pending||draft.draftPending)return
  setValues(current=>({...current,[key]:{...draft,draftPending:true,draftError:''}}))
  const {plan_id,lesson_id,answers,evidence,self_checks,date,portfolio_url,create_key,revision}=draft
  try{
   const result=await api<StoredStudyDraft>(`/study/drafts/${plan_id}/${lesson_id}`,json('PUT',{answers,evidence,self_checks,date,portfolio_url,create_key,expected_revision:revision}))
   client.setQueryData<{items:StoredStudyDraft[]}>(['study-drafts',userId,draft.course_id],old=>({items:[result,...(old?.items||[]).filter(item=>item.plan_id!==plan_id||item.lesson_id!==lesson_id)]}))
   setValues(current=>{const latest=current[key];return latest?{...current,[key]:{...latest,revision:result.revision,draftPending:false,saved:latest.create_key===create_key,draftError:''}}:current})
  }catch(error){setValues(current=>{const latest=current[key];return latest?{...current,[key]:{...latest,draftPending:false,draftError:error instanceof Error?error.message:'Не удалось сохранить черновик'}}:current})}
 }
 async function save(key:string,draft:StudyDraft){
  if(draft.pending||draft.draftPending)return
  setValues(current=>({...current,[key]:{...draft,pending:true,error:''}}))
  function finish(changes:Partial<StudyDraft>){setValues(current=>current[key]?.create_key===draft.create_key?{...current,[key]:{...current[key],...changes,pending:false}}:current)}
  try{
   const {plan_id,lesson_id,date,answers,evidence,self_checks,portfolio_url,create_key,revision}=draft
   const result=await api<Attempt>('/study/attempts',json('POST',{plan_id,lesson_id,date,answers,evidence,self_checks,portfolio_url,create_key,expected_draft_revision:revision}))
   client.setQueryData<{items:StoredStudyDraft[]}>(['study-drafts',userId,draft.course_id],old=>old?{items:old.items.filter(item=>item.plan_id!==plan_id||item.lesson_id!==lesson_id)}:old)
   finish({result,saved:false,revision:null});onSaved()
  }catch(error){finish({error:error instanceof Error?error.message:'Не удалось сохранить результат'})}
 }
 return {values,hydrate,update,saveDraft,save}
}
export type StudyDraftStore=ReturnType<typeof useStudyDrafts>
