import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, json } from '../api'
import type { Category, Expense } from '../financeTypes'
import styles from '../pages/Finance.module.css'

type Props = { categories: Category[]; currencies: string[]; defaultCurrency: string; today: string; initial?: Expense; onSaved: (expense: Expense) => void; onCancel?: () => void }
export function ExpenseForm({ categories, currencies, defaultCurrency, today, initial, onSaved, onCancel }: Props) {
  const [amount, setAmount] = useState(initial?.amount || '')
  const [currency, setCurrency] = useState(initial?.currency || defaultCurrency)
  const [category, setCategory] = useState(initial?.category_id || categories[0]?.id || '')
  const [date, setDate] = useState(initial?.date || today)
  const [note, setNote] = useState(initial?.note || '')
  const [error, setError] = useState('')
  const dirty = useRef(!!initial)
  const key = useRef(crypto.randomUUID())
  useEffect(() => { if (!dirty.current) setCurrency(defaultCurrency) }, [defaultCurrency])
  useEffect(() => { if (!dirty.current) setDate(today) }, [today])
  function changed() { dirty.current = true; key.current = crypto.randomUUID(); setError('') }
  const save = useMutation({
    mutationFn: () => {
      const normalized = amount.trim().replace(',', '.')
      if (!/^\d{1,10}(\.\d{1,2})?$/.test(normalized) || Number(normalized) <= 0 || Number(normalized) > 9999999999.99) throw new Error('Введите сумму от 0,01 до 9 999 999 999,99, не больше двух знаков после запятой.')
      return api<Expense>(initial ? `/finance/expenses/${initial.id}` : '/finance/expenses', json(initial ? 'PATCH' : 'POST', { amount: Number(normalized).toFixed(2), currency, category_id: category, date, note, ...(initial ? {} : { create_key: key.current }) }))
    },
    onSuccess: expense => {
      setError('')
      if (!initial) { setAmount(''); setNote(''); setDate(today); setCurrency(defaultCurrency); dirty.current = false; key.current = crypto.randomUUID() }
      onSaved(expense)
    },
    onError: cause => setError(cause instanceof Error ? cause.message : 'Не удалось сохранить расход'),
  })
  return <form onSubmit={event => { event.preventDefault(); if (!save.isPending) save.mutate() }} className="formStack">
    <fieldset disabled={save.isPending} className={styles.fields}>
      <div className={styles.twoColumns}>
        <label>Сумма<input required inputMode="decimal" autoComplete="off" placeholder="0,00" value={amount} onChange={event => { changed(); setAmount(event.target.value) }} /></label>
        <label>Валюта расхода<select value={currency} onChange={event => { changed(); setCurrency(event.target.value) }}>{currencies.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>Категория<select required value={category} onChange={event => { changed(); setCategory(event.target.value) }}>{categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Дата расхода<input type="date" required max={today} value={date} onChange={event => { changed(); setDate(event.target.value) }} /></label>
      </div>
      <label>Комментарий<textarea rows={2} maxLength={500} placeholder="Необязательно" value={note} onChange={event => { changed(); setNote(event.target.value) }} /></label>
      {error && <p role="alert" className="errorMessage">{error}</p>}
      <div className={styles.actions}><button className="primaryButton" type="submit">{save.isPending ? 'Сохраняем…' : initial ? 'Сохранить расход' : 'Добавить расход'}</button>{onCancel && <button type="button" className="secondaryButton" onClick={onCancel}>Отмена</button>}</div>
    </fieldset>
  </form>
}
