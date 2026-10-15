import { AssistantMaterialButton } from './SectionAssistant'
import { useState } from 'react'
import './SportLibrary.css'

type Guide = { name: string; technique: string; common_errors: string; easier_version: string; substitution: string; source: string }
type Group = 'all' | 'none' | 'bands' | 'support' | 'machines'
const groups: { id: Group; label: string }[] = [
  { id: 'all', label: 'Все' }, { id: 'none', label: 'Без оборудования' },
  { id: 'bands', label: 'Резинка' }, { id: 'support', label: 'Скамья и перекладина' },
  { id: 'machines', label: 'Тренажёры' },
]
const equipment: Record<string, Group> = {
  chair_squat: 'none', wall_pushup: 'none', glute_bridge: 'none', bird_dog: 'none', calf_raise: 'none', brisk_walk: 'none', bodyweight_squat: 'none',
  incline_pushup: 'support', step_up: 'support', supported_row: 'support',
  band_row: 'bands', band_chest_press: 'bands',
  leg_press: 'machines', chest_press: 'machines', seated_row: 'machines', lat_pulldown: 'machines',
}

export function SportLibrary({ exercises, loading = false, error = false, onRetry }: { exercises: Record<string, Guide>; loading?: boolean; error?: boolean; onRetry?: () => void }) {
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<Group>('all')
  const entries = Object.entries(exercises)
  const visible = entries.filter(([id, guide]) => (group === 'all' || equipment[id] === group) && `${guide.name} ${guide.technique}`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru')))
  return <details className="card sportLibrary" id="sport-library">
    <summary>Библиотека упражнений <span>{entries.length} карточек техники</span></summary>
    <div className="sportLibraryBody">
      <p>Найдите движение, проверьте технику и выберите посильный вариант. Личный план тренировок находится выше.</p>
      {loading ? <p>Загружаем упражнения…</p> : error ? <p role="alert">Не удалось загрузить упражнения. {onRetry && <button type="button" onClick={onRetry}>Повторить</button>}</p> : <>
        <label className="sportLibrarySearch">Найти упражнение<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Например, приседание или тяга" /></label>
        <div className="sportLibraryFilters" aria-label="Оборудование">{groups.map(item => <button key={item.id} type="button" className={group === item.id ? 'selected' : ''} aria-pressed={group === item.id} onClick={() => setGroup(item.id)}>{item.label}</button>)}</div>
        <p className="sportLibraryCount">{visible.length} {visible.length === 1 ? 'упражнение' : visible.length >= 2 && visible.length <= 4 ? 'упражнения' : 'упражнений'}</p>
        {visible.length ? <div className="sportLibraryList">{visible.map(([id, guide]) => <details key={id} className="sportLibraryItem"><summary><strong>{guide.name}</strong><span>{groups.find(item => item.id === equipment[id])?.label || 'Другое'}</span></summary><div><AssistantMaterialButton section={'sport'} material={{kind:'exercise',id}}/><p><b>Как выполнять.</b> {guide.technique}</p><p><b>Частые ошибки.</b> {guide.common_errors}</p><p><b>Если сложно.</b> {guide.easier_version}</p><p><b>Замена.</b> {guide.substitution}</p><a href={guide.source} target="_blank" rel="noreferrer">Источник техники</a></div></details>)}</div> : <p>Ничего не найдено. Попробуйте другое название или фильтр.</p>}
      </>}
      <section className="sportLibraryReading" aria-label="Материалы для начала"><h3>Как начать тренировки</h3><p>Начните с посильной нагрузки, оставляйте день отдыха между силовыми занятиями и повышайте нагрузку постепенно. Эти материалы помогут разобраться в подходах:</p><ul>
        <li><strong>Первое занятие в зале.</strong> Ознакомьтесь с базовыми движениями и настройкой оборудования. <a href="https://axgym.ru/articles/kak-nachat-trenirovatsya-muzhchine-novichku-sovety-bazovye-uprazhneniya-i-programma" target="_blank" rel="noreferrer">Статья AXGym</a></li>
        <li><strong>Тренировки дома.</strong> Подборка движений без инвентаря. Пятидневную схему автоматически не назначаем: личный план подбирается по ответам. <a href="https://goodlooker.ru/trenirovki-dlja-muzhchin-na-5-dnej.html" target="_blank" rel="noreferrer">Статья GoodLooker</a></li>
        <li><strong>Фулбоди дома.</strong> Пример занятий на всё тело и распределения нагрузки. <a href="https://goodlooker.ru/silovaya-programma-muzchiny-fullbody.html" target="_blank" rel="noreferrer">Статья GoodLooker о фулбоди</a></li>
      </ul></section>
    </div>
  </details>
}
