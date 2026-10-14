import { useState } from 'react'
import { Link } from 'react-router-dom'
import './MaterialFit.css'

export type FitAlternative = {
  id: string
  title: string
  detail?: string
  minutes?: number
  easier?: boolean
  ingredients?: string[]
  to?: string
  onSelect?: () => void
}

export type FitReason = 'other' | 'time' | 'hard' | 'equipment' | 'ingredient' | 'goal'
const reasonLabels: Record<FitReason, string> = {
  other: 'Хочу другой материал', time: 'Нет столько времени', hard: 'Слишком сложно',
  equipment: 'Нет нужного оборудования', ingredient: 'Нет продукта', goal: 'Не подходит под цель',
}

export function MaterialFit({ title, minutes, alternatives, configureTo, onConfigure, configureLabel = 'Изменить условия подбора', reasons = ['other', 'time', 'hard', 'equipment', 'ingredient', 'goal'] }: {
  title: string
  minutes?: number
  alternatives: FitAlternative[]
  configureTo?: string
  onConfigure?: () => void
  configureLabel?: string
  reasons?: FitReason[]
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState<FitReason>('other')
  const [ingredient, setIngredient] = useState('')
  const matched = alternatives.filter(item => {
    if (reason === 'time') return minutes !== undefined && item.minutes !== undefined && item.minutes < minutes
    if (reason === 'hard') return item.easier === true
    if (reason === 'equipment') return false
    if (reason === 'ingredient' && ingredient.trim()) return !item.ingredients?.some(value => value.toLocaleLowerCase('ru').includes(ingredient.trim().toLocaleLowerCase('ru')))
    return true
  }).slice(0, 3)
  return <div className="materialFit">
    <button type="button" className="textButton" aria-expanded={open} onClick={() => setOpen(value => !value)}>Мне не подходит: {title}</button>
    {open && <div className="materialFitPanel">
      <label>Почему не подходит {title}<select value={reason} onChange={event => setReason(event.target.value as FitReason)}>{reasons.map(value => <option key={value} value={value}>{reasonLabels[value]}</option>)}</select></label>
      {reason === 'ingredient' && <label>Какого продукта нет?<input type="search" value={ingredient} onChange={event => setIngredient(event.target.value)} placeholder="Название продукта" /></label>}
      {matched.length ? <><p>Другие материалы из вашей библиотеки:</p><ul>{matched.map(item => <li key={item.id}>{item.to ? <Link to={item.to}>{item.title}</Link> : <button type="button" className="textButton" onClick={item.onSelect}>{item.title}</button>}{item.detail && <small>{item.detail}</small>}</li>)}</ul></>
        : <p>Подходящей замены среди текущих материалов нет. Измените условия подбора.</p>}
      {configureTo && <Link className="secondaryButton" to={configureTo}>{configureLabel}</Link>}
      {onConfigure && <button type="button" className="secondaryButton" onClick={onConfigure}>{configureLabel}</button>}
      <p className="materialFitHint">Текущий план не изменится, пока вы сами не выберете и не подтвердите новый.</p>
    </div>}
  </div>
}
