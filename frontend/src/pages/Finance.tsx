import { Guides } from '../components/Guides'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { useLocalToday } from '../useLocalToday'
import { ExpenseForm } from '../components/ExpenseForm'
import { IncomeForm } from '../components/IncomeForm'
import { TaskDialog } from '../components/TaskDialog'
import { dateLabel, money, monthBounds, type Category, type Expense, type ExpenseList, type Income, type IncomeList, type FinanceSettings, type FinanceSummary } from '../financeTypes'
import styles from './Finance.module.css'

function previousMonth(value: string) {
  const [year, month] = value.split('-').map(Number)
  return month === 1 ? `${year - 1}-12` : `${year}-${String(month - 1).padStart(2, '0')}`
}
function monthShift(value: string, offset: number) {
  const [year, month] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1 + offset, 1))
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
}
const monthShort = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
const monthIn = ['январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']

export function FinancePage() {
  const { user } = useAuth()
  const today = useLocalToday(user?.timezone || 'Asia/Almaty')
  const client = useQueryClient()
  const [month, setMonth] = useState(today.slice(0, 7))
  const [viewCurrency, setViewCurrency] = useState('')
  const [preferred, setPreferred] = useState('')
  const [view, setView] = useState<'overview' | 'records' | 'guides'>('overview')
  const [newEntry, setNewEntry] = useState<'income' | 'expense' | null>(null)
  const [range, setRange] = useState(() => monthBounds(today.slice(0, 7)))
  const [categoryFilter, setCategoryFilter] = useState('')
  const [search, setSearch] = useState('')
  const [deleted, setDeleted] = useState(false)
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<{ expense: Expense; opener: HTMLElement } | null>(null)
  const [editingIncome, setEditingIncome] = useState<{ income: Income; opener: HTMLElement } | null>(null)
  const [notice, setNotice] = useState('')
  const [undo, setUndo] = useState<string | null>(null)
  const [undoIncome, setUndoIncome] = useState<string | null>(null)
  const [incomeOffset, setIncomeOffset] = useState(0)
  const [newCategory, setNewCategory] = useState('')
  const [categoryEdit, setCategoryEdit] = useState<{ id: string; name: string } | null>(null)
  const settings = useQuery({ queryKey: ['finance-settings', user?.id], queryFn: () => api<FinanceSettings>('/finance/settings') })
  const categories = useQuery({ queryKey: ['finance-categories', user?.id], queryFn: () => api<{ items: Category[] }>('/finance/categories') })
  const currency = viewCurrency || settings.data?.currency || 'KZT'
  const summary = useQuery({ queryKey: ['finance-summary', user?.id, month, currency, today], queryFn: () => api<FinanceSummary>(`/finance/summary?${new URLSearchParams({ month, currency })}`), enabled: !!settings.data })
  const priorMonth = previousMonth(month)
  const priorSummary = useQuery({ queryKey: ['finance-summary', user?.id, priorMonth, currency, today], queryFn: () => api<FinanceSummary>(`/finance/summary?${new URLSearchParams({ month: priorMonth, currency })}`), enabled: !!settings.data && month > '1900-01' })
  const trendMonths = Array.from({ length: 6 }, (_, index) => monthShift(month, index - 5))
  const trendQueries = useQueries({ queries: trendMonths.map(item => ({ queryKey: ['finance-summary', user?.id, item, currency, today], queryFn: () => api<FinanceSummary>(`/finance/summary?${new URLSearchParams({ month: item, currency })}`), enabled: !!settings.data })) })
  const trendMaximum = Math.max(0, ...trendQueries.map(item => Number(item.data?.month_total || 0)))
  const monthlyComparison = summary.data && priorSummary.data ? (() => {
    const difference = Number(summary.data.month_total) - Number(priorSummary.data.month_total)
    const previous = monthIn[Number(priorMonth.slice(5)) - 1]
    return difference === 0 ? `Столько же, сколько в ${previous}.` : `На ${money(Math.abs(difference).toFixed(2))} ${currency} ${difference > 0 ? 'больше' : 'меньше'}, чем в ${previous}.`
  })() : ''
  const monthLabel = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month}-01T12:00:00Z`))
  const validRange = !!range.start && !!range.end && range.start <= range.end
  const expenses = useQuery({ queryKey: ['finance-expenses', user?.id, currency, range, categoryFilter, search, deleted, offset], queryFn: () => api<ExpenseList>(`/finance/expenses?${new URLSearchParams({ currency, ...range, ...(categoryFilter ? { category_id: categoryFilter } : {}), q: search, deleted: String(deleted), limit: '30', offset: String(offset) })}`), enabled: !!settings.data && validRange })
  const incomes = useQuery({ queryKey: ['finance-incomes', user?.id, currency, range, deleted, incomeOffset], queryFn: () => api<IncomeList>(`/finance/incomes?${new URLSearchParams({ currency, ...range, deleted: String(deleted), limit: '30', offset: String(incomeOffset) })}`), enabled: !!settings.data && validRange })
  async function refresh() {
    await Promise.all([client.invalidateQueries({ queryKey: ['finance-expenses', user?.id] }), client.invalidateQueries({ queryKey: ['finance-incomes', user?.id] }), client.invalidateQueries({ queryKey: ['finance-summary', user?.id] }), client.invalidateQueries({ queryKey: ['finance-categories', user?.id] })])
  }
  const remove = useMutation({ mutationFn: (id: string) => api<void>(`/finance/expenses/${id}`, { method: 'DELETE' }), onSuccess: async (_, id) => { setUndo(id); setNotice('Расход перемещён в удалённые.'); await refresh() } })
  const restore = useMutation({ mutationFn: (id: string) => api<Expense>(`/finance/expenses/${id}/restore`, json('POST', {})), onSuccess: async () => { setUndo(null); setNotice('Расход восстановлен.'); await refresh() } })
  const removeIncome = useMutation({ mutationFn: (id: string) => api<void>(`/finance/incomes/${id}`, { method: 'DELETE' }), onSuccess: async (_, id) => { setUndoIncome(id); setUndo(null); setNotice('Доход перемещён в удалённые.'); await refresh() } })
  const restoreIncome = useMutation({ mutationFn: (id: string) => api<Income>(`/finance/incomes/${id}/restore`, json('POST', {})), onSuccess: async () => { setUndoIncome(null); setNotice('Доход восстановлен.'); await refresh() } })
  const categorySave = useMutation({
    mutationFn: (value: { id?: string; name: string }) => api<Category>(value.id ? `/finance/categories/${value.id}` : '/finance/categories', json(value.id ? 'PATCH' : 'POST', { name: value.name })),
    onSuccess: async (_, value) => { if (value.id) setCategoryEdit(null); else setNewCategory(''); await refresh() },
  })
  const settingsSave = useMutation({ mutationFn: () => api<FinanceSettings>('/finance/settings', json('PATCH', { currency: preferred || settings.data?.currency })), onSuccess: saved => {
    // Freeze the overview before changing the default for future expenses.
    setViewCurrency(currency); client.setQueryData(['finance-settings', user?.id], saved); setNotice('Основная валюта сохранена.'); setUndo(null)
  } })
  function saved(expense: Expense) { setEditing(null); setUndo(null); setNotice(`Расход сохранён: ${money(expense.amount)} ${expense.currency}, ${dateLabel(expense.date)}.`); void refresh() }
  function savedIncome(income: Income) { setEditingIncome(null); setUndoIncome(null); setNotice(`Доход сохранён: ${money(income.amount)} ${income.currency}, ${dateLabel(income.date)}.`); void refresh() }
  function changeMonth(value: string) { if (!/^\d{4}-\d{2}$/.test(value)) return; setMonth(value); setRange(monthBounds(value)); setOffset(0); setIncomeOffset(0) }
  function openEntry(kind: 'income' | 'expense') { setView('records'); setNewEntry(kind) }
  const writeError = remove.error || restore.error || removeIncome.error || restoreIncome.error || categorySave.error || settingsSave.error
  const busy = remove.isPending || restore.isPending || removeIncome.isPending || restoreIncome.isPending
  return <div className={styles.page}>
    <div className="pageHeader"><div><Link className="textButton" to="/sections">Разделы</Link><h1>Финансы</h1><p>Доходы, расходы и результат за месяц.</p></div></div>
    {(settings.isError && !settings.data) || (categories.isError && !categories.data) ? <div role="alert" className="errorMessage">Не удалось загрузить настройки финансов. <button className="textButton" onClick={() => { void settings.refetch(); void categories.refetch() }}>Повторить</button></div> : !settings.data || !categories.data ? <p className="muted">Загружаем финансы…</p> : <>
      {(settings.isError || categories.isError) && <p role="alert" className="errorMessage">Не удалось обновить настройки. Показываем последние загруженные данные; введённый расход сохранён в форме. <button className="textButton" onClick={() => { void settings.refetch(); void categories.refetch() }}>Повторить</button></p>}
      <nav className={styles.viewNav} aria-label="Разделы финансов">
        <button type="button" aria-current={view === 'overview' ? 'page' : undefined} onClick={() => setView('overview')}>Обзор</button>
        <button type="button" aria-current={view === 'records' ? 'page' : undefined} onClick={() => setView('records')}>Записи</button>
        <button type="button" aria-current={view === 'guides' ? 'page' : undefined} onClick={() => setView('guides')}>Советы</button>
      </nav>
      {notice && <div className={styles.notice} role="status"><p>{notice}</p>{undo && <button className="textButton" disabled={busy} onClick={() => restore.mutate(undo)}>Отменить удаление</button>}{undoIncome && <button className="textButton" disabled={busy} onClick={() => restoreIncome.mutate(undoIncome)}>Отменить удаление</button>}</div>}
      {writeError && <p role="alert" className="errorMessage">{writeError.message}</p>}
      <div hidden={view !== 'overview'} className={styles.viewPanel}>
      <div className={styles.overviewAction}><button type="button" className="primaryButton" onClick={() => openEntry('expense')}>Записать расход</button><button type="button" className="secondaryButton" onClick={() => openEntry('income')}>Записать доход</button></div>
      <div className={styles.overview}>
        <label>Месяц обзора<input type="month" value={month} min="1900-01" max="9999-12" onChange={event => changeMonth(event.target.value)} /></label>
        <label>Валюта обзора<select value={currency} onChange={event => { setViewCurrency(event.target.value); setOffset(0) }}>{settings.data.currencies.map(item => <option key={item}>{item}</option>)}</select></label>
      </div>
      <details className={styles.help}><summary>Как считается итог</summary><p>Каждая валюта учитывается отдельно. Разница между доходами и расходами за месяц не равна остатку на счёте.</p></details>
      {summary.isError ? <p role="alert" className="errorMessage">Не удалось загрузить итоги. <button className="textButton" onClick={() => void summary.refetch()}>Повторить</button></p> : !summary.data ? <p className="muted">Считаем финансы…</p> : <section className={styles.dashboard} aria-label="Анализ доходов и расходов">
        <div className={styles.dashboardLead}><span>Разница за {monthLabel}</span><strong data-testid="finance-net-total">{money(summary.data.net_total)} <small>{currency}</small></strong><details className={styles.insight}><summary>Подробнее об итогах</summary><p>Доходы минус расходы за месяц. Это не остаток на счёте.</p>{priorSummary.data ? <p>Расходы: {monthlyComparison}</p> : priorSummary.isError ? <p>Не удалось сравнить с прошлым месяцем. <button className="textButton" onClick={() => void priorSummary.refetch()}>Повторить</button></p> : null}{summary.data.categories.length > 0 && <p>Больше всего записано в категории «{summary.data.categories[0].name}».</p>}</details></div>
        <div className={styles.dashboardSecondary}><div><span>Доходы за месяц</span><strong data-testid="finance-income-total">{money(summary.data.income_total)} {currency}</strong><small>{summary.data.income_sources.length ? `Источников: ${summary.data.income_sources.length}` : 'Записей пока нет'}</small></div><div><span>Расходы за месяц</span><strong data-testid="finance-month-total">{money(summary.data.month_total)} {currency}</strong><small>Сегодня {money(summary.data.today_total)} · неделя {money(summary.data.week_total)}</small></div></div>
      </section>}
      <div className={styles.analyticsGrid}>
        <figure className={`card ${styles.trend}`} aria-label="Расходы за 6 месяцев"><figcaption><h2>Динамика расходов</h2><p className="muted">Шесть месяцев до выбранного, включая его · {currency}</p></figcaption>{trendQueries.some(item => item.isError) ? <p role="alert">Не удалось загрузить динамику. <button className="textButton" onClick={() => trendQueries.forEach(item => { if (item.isError) void item.refetch() })}>Повторить</button></p> : trendQueries.some(item => !item.data) ? <p className="muted">Считаем динамику…</p> : <ol className={styles.trendBars}>{trendQueries.map((item, index) => { const value = Number(item.data?.month_total || 0); const label = `${monthShort[Number(trendMonths[index].slice(5)) - 1]} ${trendMonths[index].slice(2, 4)}`; return <li key={trendMonths[index]} className={index === 5 ? styles.currentBar : ''}><span className={styles.trendAmount}>{money(value.toFixed(2))} {currency}</span><span className={styles.trendTrack}><span style={{ height: `${trendMaximum > 0 ? Math.max(value / trendMaximum * 100, value ? 5 : 0) : 0}%` }} /></span><span className={styles.trendMonth}>{label}</span></li> })}</ol>}</figure>
        <section className={`card ${styles.breakdown}`} aria-label="Расходы по категориям"><h2>Куда ушли деньги</h2><p className="muted">Доля каждого направления за {month}</p>{summary.isError ? <p>Аналитика недоступна. Повторите загрузку итогов выше.</p> : !summary.data ? <p>Загружаем…</p> : !summary.data.categories.length ? <p className="muted">В этом месяце расходов в {currency} пока нет.</p> : <div className={styles.chart}>{summary.data.categories.map(item => { const share = Number(item.amount) / Number(summary.data.month_total) * 100; return <div key={item.id}><div className={styles.chartLabel}><span>{item.name} · {share.toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%</span><strong>{money(item.amount)} {currency}</strong></div><div className={styles.bar} aria-hidden="true"><span style={{ width: `${share}%` }} /></div></div> })}</div>}</section>
      </div>
      </div>
      <div hidden={view !== 'records'} className={styles.viewPanel}>
      <div className={styles.recordActions}><div><h2>Мои записи</h2><p>Добавьте поступление или трату.</p></div><div className={styles.actions}><button type="button" className="primaryButton" onClick={() => setNewEntry(newEntry === 'expense' ? null : 'expense')}>Записать расход</button><button type="button" className="secondaryButton" onClick={() => setNewEntry(newEntry === 'income' ? null : 'income')}>Записать доход</button></div></div>
      <div className={styles.entryWorkspace}>
        <section hidden={newEntry !== 'income'} className="card"><h2>Новый доход</h2><IncomeForm currencies={settings.data.currencies} defaultCurrency={settings.data.currency} today={today} onSaved={savedIncome} /></section>
        <section hidden={newEntry !== 'expense'} className="card"><h2>Новый расход</h2><ExpenseForm categories={categories.data.items} currencies={settings.data.currencies} defaultCurrency={settings.data.currency} today={today} onSaved={saved} /></section>
      </div>
      <details className={`card ${styles.historyFilters}`}><summary>Поиск и фильтры записей</summary><div className={styles.filters}>
          <label>С<input type="date" value={range.start} onChange={event => { setRange({ ...range, start: event.target.value }); setOffset(0) }} /></label>
          <label>По<input type="date" value={range.end} onChange={event => { setRange({ ...range, end: event.target.value }); setOffset(0) }} /></label>
          <label>Категория в истории<select value={categoryFilter} onChange={event => { setCategoryFilter(event.target.value); setOffset(0) }}><option value="">Все категории</option>{categories.data.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Поиск<input type="search" maxLength={100} placeholder="Комментарий или категория" value={search} onChange={event => { setSearch(event.target.value); setOffset(0) }} /></label>
          <label>Статус записей<select value={String(deleted)} onChange={event => { setDeleted(event.target.value === 'true'); setOffset(0) }}><option value="false">Активные</option><option value="true">Удалённые</option></select></label>
        </div><p className="muted">Категория и поиск действуют только на расходы.</p></details>
      <section className="card"><h2>История доходов</h2>
        {!validRange ? <p role="alert" className="errorMessage">Укажите корректный период выше.</p> : incomes.isError ? <p role="alert" className="errorMessage">Не удалось загрузить доходы. <button className="textButton" onClick={() => void incomes.refetch()}>Повторить</button></p> : !incomes.data ? <p className="muted">Загружаем доходы…</p> : <>
          {!incomes.data.items.length ? <p className="muted">За выбранный период доходов в {currency} нет.</p> : <div className={styles.list}>{incomes.data.items.map(item => <article className={styles.row} key={item.id}>
            <div className={styles.rowContent}><strong>{item.source}</strong>{item.note && <p>{item.note}</p>}<small>{dateLabel(item.date)}</small></div>
            <div className={styles.rowActions}><strong>+{money(item.amount)} {item.currency}</strong><div className={styles.actions}>{item.deleted ? <button className="secondaryButton" disabled={busy} onClick={() => restoreIncome.mutate(item.id)}>Восстановить доход</button> : <><button className="textButton" disabled={busy} aria-label={`Изменить доход ${item.source}`} onClick={event => setEditingIncome({ income: item, opener: event.currentTarget })}>Изменить</button><button className="textButton" disabled={busy} aria-label={`Удалить доход ${item.source}`} onClick={() => removeIncome.mutate(item.id)}>Удалить</button></>}</div></div>
          </article>)}</div>}
          <div className={styles.actions}><span className="muted">Всего: {incomes.data.total}</span>{incomeOffset > 0 && <button className="secondaryButton" onClick={() => setIncomeOffset(Math.max(0, incomeOffset - 30))}>Назад</button>}{incomeOffset + 30 < incomes.data.total && <button className="secondaryButton" onClick={() => setIncomeOffset(incomeOffset + 30)}>Далее</button>}</div>
        </>}
      </section>
      <section className="card"><h2>История расходов</h2>

        {!validRange ? <p role="alert" className="errorMessage">Укажите начало и конец периода. Начало должно быть не позже конца.</p> : expenses.isError ? <p role="alert" className="errorMessage">Не удалось загрузить историю. <button className="textButton" onClick={() => void expenses.refetch()}>Повторить</button></p> : !expenses.data ? <p className="muted">Загружаем историю…</p> : <>
          {!expenses.data.items.length ? <p className="muted">По выбранным фильтрам расходов нет.</p> : <div className={styles.list}>{expenses.data.items.map(item => <article className={styles.row} key={item.id}>
            <div className={styles.rowContent}><strong>{item.category_name}</strong><p>{item.note}</p><small>{dateLabel(item.date)}</small></div>
            <div className={styles.rowActions}><strong>{money(item.amount)} {item.currency}</strong><div className={styles.actions}>{item.deleted ? <button className="secondaryButton" disabled={busy} onClick={() => restore.mutate(item.id)}>Восстановить расход</button> : <><button className="textButton" disabled={busy} aria-label={`Изменить расход ${item.note || item.category_name}`} onClick={event => setEditing({ expense: item, opener: event.currentTarget })}>Изменить</button><button className="textButton" disabled={busy} aria-label={`Удалить расход ${item.note || item.category_name}`} onClick={() => remove.mutate(item.id)}>Удалить</button></>}</div></div>
          </article>)}</div>}
          <div className={styles.actions}><span className="muted">Всего: {expenses.data.total}{expenses.data.total > 0 && ` · ${offset + 1}–${Math.min(offset + 30, expenses.data.total)}`}</span>{offset > 0 && <button className="secondaryButton" onClick={() => setOffset(Math.max(0, offset - 30))}>Назад</button>}{offset + 30 < expenses.data.total && <button className="secondaryButton" onClick={() => setOffset(offset + 30)}>Далее</button>}</div>
        </>}
      </section>
      <details className={`card ${styles.settings}`}><summary>Категории и валюта</summary><div className={styles.workspace}>
        <section><h2>Ваши категории</h2><form className="formStack" onSubmit={event => { event.preventDefault(); categorySave.mutate({ name: newCategory }) }}><label>Название новой категории<input required maxLength={60} value={newCategory} disabled={categorySave.isPending} onChange={event => setNewCategory(event.target.value)} /></label><button className="secondaryButton" disabled={categorySave.isPending}>Добавить категорию</button></form>
          <ul className={styles.categoryList}>{categories.data.items.map(item => <li key={item.id}><span>{item.name}</span><button className="textButton" disabled={categorySave.isPending} aria-label={`Изменить категорию ${item.name}`} onClick={() => setCategoryEdit({ ...item })}>Изменить</button></li>)}</ul>
          {categoryEdit && <form className="formStack" onSubmit={event => { event.preventDefault(); categorySave.mutate(categoryEdit) }}><label>Новое название категории<input required maxLength={60} value={categoryEdit.name} disabled={categorySave.isPending} onChange={event => setCategoryEdit({ ...categoryEdit, name: event.target.value })} /></label><div className={styles.actions}><button className="primaryButton" disabled={categorySave.isPending}>Сохранить категорию</button><button className="secondaryButton" type="button" disabled={categorySave.isPending} onClick={() => setCategoryEdit(null)}>Отмена</button></div></form>}
        </section>
        <section><h2>Валюта новых расходов</h2><p className="muted">Изменение действует на новые записи. Уже сохранённые расходы и незавершённый ввод сохранят свою валюту.</p><form className="formStack" onSubmit={event => { event.preventDefault(); settingsSave.mutate() }}><label>Основная валюта<select value={preferred || settings.data.currency} disabled={settingsSave.isPending} onChange={event => setPreferred(event.target.value)}>{settings.data.currencies.map(item => <option key={item}>{item}</option>)}</select></label><button className="secondaryButton" disabled={settingsSave.isPending}>Сохранить валюту</button></form></section>
      </div></details>
      </div>
      <div hidden={view !== 'guides'} className={styles.viewPanel}><Guides area="finance" /></div>
      {editing && <TaskDialog label="Редактировать расход" onClose={() => setEditing(null)} returnFocusTo={editing.opener}><section className={`card ${styles.dialog}`}><h2>Редактировать расход</h2><ExpenseForm key={editing.expense.id} initial={editing.expense} categories={categories.data.items} currencies={settings.data.currencies} defaultCurrency={settings.data.currency} today={today} onSaved={saved} onCancel={() => setEditing(null)} /></section></TaskDialog>}
      {editingIncome && <TaskDialog label="Редактировать доход" onClose={() => setEditingIncome(null)} returnFocusTo={editingIncome.opener}><section className={`card ${styles.dialog}`}><h2>Редактировать доход</h2><IncomeForm key={editingIncome.income.id} initial={editingIncome.income} currencies={settings.data.currencies} defaultCurrency={settings.data.currency} today={today} onSaved={savedIncome} onCancel={() => setEditingIncome(null)} /></section></TaskDialog>}
    </>}
  </div>
}
