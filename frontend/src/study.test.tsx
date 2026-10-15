import {fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {MemoryRouter} from 'react-router-dom'
import {beforeEach,vi} from 'vitest'
import {StudyPage} from './pages/Study'
import {StudyPlanForm} from './components/StudyPlanForm'
import {StudyCards} from './components/StudyCards'
import {StudyDay} from './components/StudyDay'
import type {StoredStudyDraft} from './useStudyDrafts'
import type {Course,Lesson} from './studyTypes'
const {apiMock,dayState}=vi.hoisted(()=>({apiMock:vi.fn(),dayState:{value:'2026-10-10'}}))
vi.mock('./api',async original=>({...await original<typeof import('./api')>(),api:apiMock}))
vi.mock('./auth',()=>({useAuth:()=>({user:{id:'one',timezone:'Asia/Almaty'}})}))
vi.mock('./useLocalToday',()=>({useLocalToday:()=> dayState.value}))
const lesson={id:'en-a2-01',title:'Обычный день',level:'A2',minutes:30,explanation:['Объяснение грамматики.','Пример применения.'],example:'I work.',practice:'Напишите о своём дне.',retry_practice:'Составьте три новые фразы о своём дне с he или she, проверьте окончание -s.',solution:'Используйте настоящее время.',rubric:['Я написал текст','Я проверил грамматику','Я говорил вслух'],quiz:[{prompt:'Choose the verb',options:['works','work'],skill:'grammar'}],reading:'An original story.',transcript:'An original recording.',audio:'/audio/study-v1/en-a2-01.wav',speaking:'Расскажите о дне',vocabulary:[{id:'word',word:'routine',translation:'распорядок',example:'My routine.'}]}
const course:Course={id:'english',version:'v1',area:'languages',title:'Английский A2 → B2',intro:'Готовый маршрут',prerequisite:'Нужен A1',levels:['A2','B1','B2'],sources:[],lessons:[lesson as Lesson]}
const plan={id:'p1',course_id:'english',version:'v1',level:'A2',goal:'general',minutes:30,weekdays:[0,2,4],start_date:'2026-10-10',lesson_ids:[lesson.id],archived:false,created_at:'2026-10-10T00:00:00'}
let active: typeof plan|null
let archived:boolean
let fail:boolean
let submissions:Record<string,unknown>[]
let reviewed:boolean
let storedDraft:StoredStudyDraft|null
let failDraft:boolean
beforeEach(()=>{dayState.value='2026-10-10';course.lessons=[lesson];active={...plan};archived=false;fail=false;submissions=[];reviewed=false;storedDraft=null;failDraft=false;apiMock.mockReset().mockImplementation(async(path:string,init?:RequestInit)=>{
 const body=init?.body?JSON.parse(init.body as string):{}
 if(path==='/study/grammar-check')return {correct:body.answer==='studies',explanation:'С she в привычке нужна форма studies.'}
 if(path.startsWith('/study/assist/availability'))return {question_indices:[0]}
 if(path==='/study/assist'){submissions.push(body);return {request_id:'req1',source:'authored',text:body.stage==='hint'?'Намёк из урока':'Следующий шаг из урока',next_stage_token:body.stage==='hint'?'step-token':null,stage:body.stage}}
 if(path==='/study/assist/feedback'){submissions.push(body);return {saved:true}}
 if(path.startsWith('/study/courses/'))return course
 if(path.startsWith('/study/state/'))return {active_plan:active,plan:active?{...active,archived}:null,plans:active?[active]:[],completed:[],next_lesson_id:lesson.id,attempts:[],attempt_total:0,history_offset:0}
 if(path==='/study/drafts/english')return {items:storedDraft?[storedDraft]:[]}
 if(path.startsWith('/study/drafts/p1/')){submissions.push(body);if(failDraft){failDraft=false;throw new Error('Черновик не сохранён')}if((storedDraft?.revision??null)!==body.expected_revision)throw new Error('Черновик больше не найден');storedDraft={id:'d1',plan_id:'p1',lesson_id:lesson.id,revision:(storedDraft?.revision as number||0)+1,updated_at:'2026-10-10T00:00:00',content:{answers:body.answers,evidence:body.evidence,self_checks:body.self_checks,date:body.date,portfolio_url:body.portfolio_url,create_key:body.create_key}};return storedDraft}
 if(path==='/study/preview')return {...body,lesson_count:1,lesson_ids:[lesson.id],sessions_per_lesson:1,reason:'Выбран A2 и три дня',prerequisite:'Нужен A1'}
 if(path==='/study/plans'){submissions.push(body);active={...plan};return active}
 if(path==='/study/attempts'){submissions.push(body);if(fail){fail=false;throw new Error('Сеть недоступна')}if(storedDraft&&storedDraft.revision!==body.expected_draft_revision)throw new Error('Черновик изменён');storedDraft=null;return {id:'a1',plan_id:'p1',lesson_id:lesson.id,date:body.date,snapshot:lesson,score:0,total:1,passed:false,feedback:[{prompt:'Choose the verb',correct:false,answer:'work',accepted:['works'],explanation:'После she требуется -s.'}],evidence:body.evidence,self_checks:body.self_checks,assessment:'Самооценка',portfolio_url:''}}
 if(path.startsWith('/study/cards/'))return {items:reviewed?[]:[{...lesson.vocabulary[0],review_id:null,due_date:'2026-10-10'}],total_learned:1,today:'2026-10-10'}
 if(path==='/study/reviews'){submissions.push(body);reviewed=true;return {id:'r1',due_date:'2026-10-11'}}
 if(path.startsWith('/study/day?'))return {items:[{course_id:'english',course_title:course.title,plan_id:'p1',lesson_id:lesson.id,title:lesson.title,date:'2026-10-10',minutes:30}],notice:'Текущий шаг'}
 throw new Error(path)
})})
function mount(url='/languages',day=false,client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})){const view=render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}>{day?<StudyDay date="2026-10-10"/>:<StudyPage courseId="english"/>}</MemoryRouter></QueryClientProvider>);return {client,...view}}
test('course view marks its lesson layout for the language theme',async()=>{
 const view=mount()
 await screen.findByRole('heading',{name:/Английский A2/})
 expect(view.container.querySelector('[data-course-kind="language"]')).toBeInTheDocument()
})
async function openPractice(){fireEvent.click(await screen.findByRole('button',{name:/Практика и результат/}));return screen.findByLabelText('Ваш результат и заметки')}
test('english route offers level-specific optional practice with direct tasks',async()=>{
 mount()
 const section=await screen.findByText('Практика после урока')
 expect(section.closest('details')).not.toHaveAttribute('open')
 fireEvent.click(section)
 const listening=screen.getByRole('link',{name:/Аудирование A2/})
 expect(listening).toHaveAttribute('href','https://learnenglish.britishcouncil.org/free-resources/listening/a2')
 expect(screen.getByRole('link',{name:/Чтение A2/})).toHaveAttribute('href','https://learnenglish.britishcouncil.org/free-resources/reading/a2')
 expect(screen.getByText(/Послушайте запись/)).toBeInTheDocument()
})
test('english lesson shows one clear step at a time and lesson words reveal on demand',async()=>{
 mount()
 const steps=await screen.findByRole('navigation',{name:'Шаги урока'})
 expect(screen.getByText('Объяснение грамматики.')).toBeVisible()
 expect(screen.getByText('Напишите о своём дне.')).not.toBeVisible()
 fireEvent.click(within(steps).getByRole('button',{name:/Выучить слова/}))
 expect(screen.getByText('Слова урока')).toBeVisible()
 expect(screen.queryByText('распорядок')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Показать перевод'}))
 expect(screen.getByText('распорядок')).toBeVisible()
 fireEvent.click(within(steps).getByRole('button',{name:/Читать и слушать/}))
 expect(screen.getByText('An original story.')).toBeVisible()
 fireEvent.click(within(steps).getByRole('button',{name:/Практика и результат/}))
 expect(screen.getByLabelText('Ваш результат и заметки')).toBeVisible()
})
test('grammar check explains a wrong answer without saving a final attempt',async()=>{
 course.version='v3';active={...plan,version:'v3'}
 course.lessons=[{...lesson,grammar:{kind:'grammar',rule:'Present Simple describes habits. Use the -s form with she.',table:{headers:['Форма','Использование'],rows:[['She studies','Привычка'],['She is studying','Сейчас']]},examples:['She studies every day.','She is studying now.'],check:{prompt:'She ___ every day.',options:['is study','studies'],explanation:'С she в привычке нужна форма studies.'}}}]
 mount()
 expect(await screen.findByText('Present Simple describes habits. Use the -s form with she.')).toBeVisible()
 fireEvent.click(screen.getByLabelText('is study'))
 fireEvent.click(screen.getByRole('button',{name:'Проверить правило'}))
 expect(await screen.findByRole('status')).toHaveTextContent('С she в привычке нужна форма studies.')
 expect(submissions).toHaveLength(0)
})
test('lesson help opens a staged hint and keeps free text private by default',async()=>{
 mount();await openPractice()
 fireEvent.change(screen.getByLabelText('Ваш результат и заметки'),{target:{value:'Мой личный текст решения для проверки.'}})
 fireEvent.click(await screen.findByRole('button',{name:'Намёк'}))
 expect(await screen.findByText('Намёк из урока')).toBeInTheDocument()
 expect(screen.getByText('Готовое объяснение из урока')).toBeInTheDocument()
 expect(submissions.at(-1)?.answer_text).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'Следующий шаг'}))
 expect(await screen.findByText('Следующий шаг из урока')).toBeInTheDocument()
 expect(submissions.at(-1)?.stage).toBe('next_step')
 fireEvent.click(screen.getByRole('button',{name:'Помогло'}))
 expect(await screen.findByText('Спасибо за оценку')).toBeInTheDocument()
 expect(submissions.at(-1)).toEqual({request_id:'req1',helped:true})
})
test('next material opens an existing lesson without replacing the plan',async()=>{
 const next={...lesson,id:'en-a2-02',title:'Следующая тема'}
 course.lessons=[lesson,next];active={...plan,lesson_ids:[lesson.id,next.id]}
 mount();await openPractice()
 fireEvent.click(screen.getByRole('button',{name:'Посмотреть следующий материал'}))
 expect(await screen.findByRole('heading',{name:'Следующая тема'})).toBeInTheDocument()
 expect(submissions).toHaveLength(0)
})
test('unsuitable lesson offers an earlier lesson in the same saved plan',async()=>{
 const next={...lesson,id:'en-a2-02',title:'Рабочий день',minutes:45}
 course.lessons=[lesson,next]
 active={...plan,lesson_ids:[lesson.id,next.id]}
 mount('/languages?plan=p1&lesson=en-a2-02')
 fireEvent.click(await screen.findByRole('button',{name:'Мне не подходит: Рабочий день'}))
 fireEvent.change(screen.getByLabelText('Почему не подходит Рабочий день'),{target:{value:'hard'}})
 expect(screen.getByRole('link',{name:'Обычный день'})).toHaveAttribute('href','/languages?plan=p1&lesson=en-a2-01')
})
test('chapter dictionary opens cards from the selected lesson and preserves review separately',async()=>{
 mount()
 fireEvent.click(await screen.findByRole('button',{name:'Словарь и повторение'}))
 expect(screen.getByRole('heading',{name:'Словарь по главам'})).toBeInTheDocument()
 expect(screen.getByRole('heading',{name:'routine'})).toBeInTheDocument()
 expect(screen.queryByText('распорядок')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Показать значение'}))
 expect(screen.getByText('распорядок')).toBeInTheDocument()
 expect(screen.getByText('Повторить изученные слова по сроку')).toBeInTheDocument()
})
test('plan preview requires explicit activation',async()=>{
 active=null;mount()
 fireEvent.click(await screen.findByRole('button',{name:'Посмотреть план'}))
 expect(await screen.findByText('Выбран A2 и три дня')).toBeInTheDocument()
 expect(submissions).toHaveLength(0)
 fireEvent.click(screen.getByRole('button',{name:'Начать этот план'}))
 await screen.findByRole('heading',{name:'Обычный день'})
 expect(submissions[0].expected_plan_id).toBeNull()
})
test('failed lesson save retains evidence and retry identity then shows grading explanation',async()=>{
 fail=true;mount();await openPractice()
 fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Самостоятельный текст с описанием моего дня.'}})
 fireEvent.click(screen.getByLabelText('work'))
 fireEvent.click(screen.getByRole('button',{name:'Проверить и сохранить'}))
 await screen.findByText('Сеть недоступна')
 expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Самостоятельный текст с описанием моего дня.')
 fireEvent.click(screen.getByRole('button',{name:'Проверить и сохранить'}))
 await screen.findByText('После she требуется -s.')
 expect(submissions[0].create_key).toBe(submissions[1].create_key)
 expect(screen.getByText(/Есть что повторить/)).toBeInTheDocument()
 expect(screen.getByText(lesson.retry_practice)).toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'Сохранить черновик'})).not.toBeInTheDocument()
})
test('archived plan shows materials and prevents a stale submission',async()=>{
 archived=true;mount('/languages?plan=p1&lesson=en-a2-01')
 expect(await screen.findByText(/Архивный план/)).toBeInTheDocument()
 expect(apiMock).toHaveBeenCalledWith('/study/courses/english?version=v1')
 expect(screen.queryByRole('button',{name:'Проверить и сохранить'})).not.toBeInTheDocument()
 expect(screen.getByRole('heading',{name:'Обычный день'})).toBeInTheDocument()
})
test('new plan loads the latest course only after the saved-plan state',async()=>{
 active=null;mount()
 await screen.findByRole('button',{name:'Посмотреть план'})
 expect(apiMock).toHaveBeenCalledWith('/study/courses/english')
})
test('vocabulary reveal and review persist then remove due card',async()=>{
 mount();fireEvent.click(await screen.findByRole('button',{name:'Словарь и повторение'}));fireEvent.click(screen.getByText('Повторить изученные слова по сроку'))
 fireEvent.click(await screen.findByRole('button',{name:'Показать перевод'}))
 expect(screen.getByText('распорядок',{selector:'strong'})).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Вспомнил'}))
 await waitFor(()=>expect(screen.getByText(/На сегодня всё повторено/)).toBeInTheDocument())
 expect(submissions[0]).toMatchObject({expected_review_id:null,card_id:'word'})
})
test('the current route offers a direct retry for a failed practice attempt',async()=>{
 const original=apiMock.getMockImplementation()!
 apiMock.mockImplementation(async(path:string,init?:RequestInit)=>{
  const result=await original(path,init)
  return path.startsWith('/study/state/')?{...result,attempt_total:1,pending_retry_lesson_id:lesson.id,attempts:[]}:result
 })
 mount()
 expect(await screen.findByText('Повторить: Обычный день')).toBeInTheDocument()
 expect(screen.getByText(lesson.retry_practice)).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Открыть повторение'}))
 expect(screen.getByRole('heading',{name:'Обычный день'})).toBeInTheDocument()
})
test('daily lesson link preserves plan lesson and selected date',async()=>{
 mount('/',true)
 const link=await screen.findByRole('link',{name:/Обычный день/})
 expect(link).toHaveAttribute('href','/languages?plan=p1&lesson=en-a2-01&date=2026-10-10')
})


test('pending failed save remains recoverable after switching lessons',async()=>{
 const second={...lesson,id:'en-a2-02',title:'Второй урок'};course.lessons=[lesson,second];active={...plan,lesson_ids:[lesson.id,second.id]}
 const original=apiMock.getMockImplementation()!;let rejectSave!:(error:Error)=>void
 apiMock.mockImplementation((path:string,init?:RequestInit)=>path==='/study/attempts'?new Promise((_,reject)=>{rejectSave=reject}):original(path,init))
 mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Важный черновик первого урока, который нельзя потерять.'}})
 fireEvent.click(screen.getByLabelText('work'));fireEvent.click(screen.getByRole('button',{name:'Проверить и сохранить'}))
 await waitFor(()=>expect(rejectSave).toBeDefined())
 fireEvent.click(screen.getByRole('button',{name:/2. Второй урок/}))
 expect(await screen.findByRole('heading',{name:'Второй урок'})).toBeInTheDocument()
 rejectSave(new Error('Отложенная ошибка сети'))
 fireEvent.click(screen.getByRole('button',{name:/1. Обычный день/}))
 await openPractice()
 expect(await screen.findByLabelText('Ваш результат и заметки')).toHaveValue('Важный черновик первого урока, который нельзя потерять.')
 expect(await screen.findByText('Отложенная ошибка сети')).toBeInTheDocument()
})

test('remote plan replacement retains a copyable draft and delayed error',async()=>{
 const original=apiMock.getMockImplementation()!;let rejectSave!:(error:Error)=>void
 apiMock.mockImplementation((path:string,init?:RequestInit)=>path==='/study/attempts'?new Promise((_,reject)=>{rejectSave=reject}):original(path,init))
 const view=mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Черновик архивного плана должен остаться доступным.'}})
 fireEvent.click(screen.getByLabelText('work'));fireEvent.click(screen.getByRole('button',{name:'Проверить и сохранить'}))
 await waitFor(()=>expect(rejectSave).toBeDefined());archived=true
 await view.client.invalidateQueries({queryKey:['study-state']})
 rejectSave(new Error('План уже заменён'))
 expect(await screen.findByLabelText('Ваш результат и заметки')).toHaveValue('Черновик архивного плана должен остаться доступным.')
 expect(await screen.findByText('План уже заменён',{exact:true})).toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'Проверить и сохранить'})).not.toBeInTheDocument()
})

test('history pagination cannot discard a hidden lesson draft',async()=>{
 const original=apiMock.getMockImplementation()!
 apiMock.mockImplementation(async(path:string,init?:RequestInit)=>{const result=await original(path,init);return path.startsWith('/study/state/')?{...result,attempt_total:41}:result})
 mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Черновик до перехода к более ранней истории.'}})
 fireEvent.click(screen.getByRole('button',{name:'История результатов'}));fireEvent.click(screen.getByRole('button',{name:'Более ранние результаты'}))
 await screen.findByText(/Показаны 21–40/)
 fireEvent.click(screen.getByRole('button',{name:'Уроки и главы'}))
 expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Черновик до перехода к более ранней истории.')
})

test('refreshed active plan cannot silently retarget an existing replacement preview',async()=>{
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});const onSaved=vi.fn()
 const element=(p:typeof plan)=><QueryClientProvider client={client}><StudyPlanForm course={course} active={p} today="2026-10-10" onSaved={onSaved}/></QueryClientProvider>
 const view=render(element(plan));fireEvent.click(screen.getByRole('button',{name:'Посмотреть план'}));await screen.findByRole('button',{name:'Подтвердить замену плана'})
 view.rerender(element({...plan,id:'p2'}))
 const confirm=screen.getByRole('button',{name:'Подтвердить замену плана'})
 expect(confirm).toBeDisabled()
 expect(screen.getByText(/План изменился.*предпросмотр/)).toBeInTheDocument()
})

test('due cards refresh at local midnight without focus or remount',async()=>{
 reviewed=true;const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 const element=()=><QueryClientProvider client={client}><StudyCards courseId="english" version="v1"/></QueryClientProvider>
 const view=render(element());await screen.findByText(/На сегодня всё повторено/)
 reviewed=false;dayState.value='2026-10-11';view.rerender(element())
 expect(await screen.findByRole('heading',{name:/^routine$/})).toBeInTheDocument()
})

test('compact lesson selector opens a chosen lesson while keeping the plan context',async()=>{
 const second={...lesson,id:'en-a2-02',title:'Второй урок'};course.lessons=[lesson,second];active={...plan,lesson_ids:[lesson.id,second.id]}
 mount('/languages?plan=p1&lesson=en-a2-01&date=2026-10-10')
 expect(await screen.findByRole('link',{name:'К занятию'})).toHaveAttribute('href','#study-lesson')
 const selector=await screen.findByRole('combobox',{name:'Выбрать урок'})
 fireEvent.change(selector,{target:{value:'en-a2-02'}})
 expect(await screen.findByRole('heading',{name:'Второй урок'})).toBeInTheDocument()
 await openPractice()
 expect(screen.getByLabelText('Дата занятия')).toHaveValue('2026-10-10')
})

test('an unfinished lesson draft saved on the server survives leaving and reopening the route',async()=>{
 const view=mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Мой текст будет нужен после перезагрузки страницы.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 expect(await screen.findByText('Черновик сохранён на сервере.')).toBeInTheDocument()
 view.unmount();mount();await openPractice()
 await waitFor(()=>expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Мой текст будет нужен после перезагрузки страницы.'))
})

test('failed draft save retains the text and offers a retry without claiming success',async()=>{
 failDraft=true;mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Личный текст остаётся в форме при ошибке.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 expect(await screen.findByText('Черновик не сохранён')).toBeInTheDocument()
 expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Личный текст остаётся в форме при ошибке.')
 expect(screen.queryByText('Черновик сохранён на сервере.')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 expect(await screen.findByText('Черновик сохранён на сервере.')).toBeInTheDocument()
 expect(submissions[0].create_key).toBe(submissions[1].create_key)
})

test('after a confirmed attempt another practice draft can be saved without an obsolete revision',async()=>{
 mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Первая достаточно длинная учебная попытка.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 await screen.findByText('Черновик сохранён на сервере.')
 fireEvent.click(screen.getByLabelText('work'))
 fireEvent.click(screen.getByRole('button',{name:'Проверить и сохранить'}))
 await screen.findByText('Результат сохранён.',{exact:true})
 fireEvent.change(screen.getByLabelText('Ваш результат и заметки'),{target:{value:'Новая практика по объяснению ошибки и повторению темы.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 await screen.findByText('Черновик сохранён на сервере.')
 expect(storedDraft?.content.evidence).toBe('Новая практика по объяснению ошибки и повторению темы.')
 expect(submissions.at(-1)?.expected_revision).toBeNull()
})

test('course revisit with one query cache restores the newest saved server revision',async()=>{
 const view=mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Первый текст сохранённого черновика.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 await screen.findByText('Черновик сохранён на сервере.')
 const client=view.client;view.unmount()
 storedDraft={...storedDraft!,revision:2,content:{...storedDraft!.content,evidence:'Новый текст со второго устройства.'}}
 mount('/languages',false,client);await openPractice()
 await waitFor(()=>expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Новый текст со второго устройства.'))
})

test('a newer server revision replaces untouched saved text after draft refresh',async()=>{
 const view=mount();await openPractice();fireEvent.change(await screen.findByLabelText('Ваш результат и заметки'),{target:{value:'Первый текст сохранённого черновика.'}})
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик'}))
 await screen.findByText('Черновик сохранён на сервере.')
 storedDraft={...storedDraft!,revision:2,content:{...storedDraft!.content,evidence:'Свежий текст с другого устройства.'}}
 await view.client.invalidateQueries({queryKey:['study-drafts']})
 await waitFor(()=>expect(screen.getByLabelText('Ваш результат и заметки')).toHaveValue('Свежий текст с другого устройства.'))
})

test('lesson jump opens lesson from history tab',async()=>{
 mount();fireEvent.click(await screen.findByRole('button',{name:'История результатов'}))
 fireEvent.click(screen.getByRole('link',{name:'К занятию'}))
 expect(screen.getByRole('button',{name:'Уроки и главы'})).toHaveAttribute('aria-pressed','true')
})
