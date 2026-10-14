export type Category = { id: string; name: string }
export type FinanceSettings = { currency: string; currencies: string[] }
export type Expense = { id: string; amount: string; currency: string; category_id: string; category_name: string; date: string; note: string; deleted: boolean }
export type ExpenseList = { items: Expense[]; total: number; offset: number; limit: number }
export type Income = { id: string; amount: string; currency: string; source: string; date: string; note: string; deleted: boolean }
export type IncomeList = { items: Income[]; total: number; offset: number; limit: number }
export type FinanceSummary = { currency: string; today: string; week_start: string; week_end: string; month: string; today_total: string; week_total: string; month_total: string; income_total: string; net_total: string; income_sources: { name: string; amount: string }[]; categories: { id: string; name: string; amount: string }[] }
export const money = (amount: string) => Number(amount).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const dateLabel = (value: string) => value.split('-').reverse().join('.')
export function monthBounds(month: string) {
  const [year, number] = month.split('-').map(Number)
  return { start: `${month}-01`, end: `${month}-${new Date(Date.UTC(year, number, 0)).getUTCDate()}` }
}
