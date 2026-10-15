import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { NutritionPage } from './pages/Nutrition'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one', timezone: 'Asia/Almaty' } }) }))

const recipe = { id: 'oatmeal', name: 'Овсяная каша с бананом', meal: 'breakfast', minutes: 12, servings: 2, cost_tier: 'low', vegetarian: true, allergens: ['milk'], ingredients: [{ food_id: 'oats', grams: 80, state: 'dry' }, { food_id: 'banana', grams: 100, state: 'raw' }], steps: ['Сварите кашу.'], nutrition_per_serving: { kcal: 250, protein_g: 10, fat_g: 5, carbs_g: 35 } }
const recipes = { version: '1', basis: 'Пищевая ценность исходных продуктов.', foods: { oats: { name: 'Овсяные хлопья', state: 'dry', source_url: 'https://example.org/oats' }, banana: { name: 'Банан', state: 'raw', source_url: 'https://example.org/banana' } }, recipes: [recipe] }
const estimate = { estimate: { resting_kcal: 1780, maintenance_kcal: 2723, target_kcal: 2451, protein_g: 112, fat_g: 82, carbs_g: 316, explanation: 'Ориентир по формуле.', limits: 'Это оценка.' }, reasons: [], sources: { formula: 'https://pubmed.ncbi.nlm.nih.gov/2305711/' } }
const answers = { age: 30, height_cm: 180, weight_kg: 80, formula_sex: 'male', activity: 'light', goal: 'fat_loss', pregnant: false, breastfeeding: false, special_condition: false }
const preferences = { vegetarian: true, allergies: ['milk'], excluded_food_ids: [], budget: 'low', max_minutes: 30 }

function mount(entry = '/health/nutrition') {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[entry]}><NutritionPage view={entry.startsWith('/health/calories') ? 'calculator' : 'nutrition'} /></MemoryRouter></QueryClientProvider>)
}

test('recipe preferences are optional and recipes remain the first visible content', async () => {
  apiMock.mockReset().mockResolvedValue(recipes)
  mount()
  expect(await screen.findByText('Овсяная каша с бананом')).toBeInTheDocument()
  expect(screen.getByText('Настроить подбор').closest('details')).not.toHaveAttribute('open')
  fireEvent.click(screen.getByText('Настроить подбор'))
  expect(screen.getByText('Настроить подбор').closest('details')).toHaveAttribute('open')
  expect(screen.getByLabelText('Показывать сначала')).toBeInTheDocument()
})

test('unmapped recipe uses a stable photo placeholder', async () => {
  apiMock.mockReset().mockResolvedValue({ ...recipes, recipes: [{ ...recipe, id: 'new_unmapped_dish' }] })
  mount()
  await screen.findByText('Овсяная каша с бананом')
  expect(screen.getByText('Фото не добавлено')).toHaveClass('nutritionRecipePhoto--placeholder')
})

test('nutrition contains recipes and recalculates ingredient grams for selected portions', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/nutrition/recipes') return recipes
    throw new Error(`Unexpected ${path}`)
  })
  mount('/health/nutrition?recipe=oatmeal')
  const details = (await screen.findByText('Овсяная каша с бананом')).closest('details')!
  expect(details).toHaveAttribute('open')
  expect(within(details).getByText('Овсяные хлопья')).toBeInTheDocument()
  expect(within(details).getByText('80 г')).toBeInTheDocument()
  fireEvent.change(within(details).getByLabelText('Количество порций'), { target: { value: '3' } })
  expect(within(details).getByText('120 г')).toBeInTheDocument()
  expect(within(details).getByText('150 г')).toBeInTheDocument()
  expect(within(details).getByText('Продукты: 270 г на 3 порц.')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Рацион на неделю' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Настройки меню' })).not.toBeInTheDocument()
  expect(apiMock).toHaveBeenCalledTimes(1)
})

test('cooking mode shows one step, tracks ingredients and returns to recipe', async () => {
  apiMock.mockReset().mockResolvedValue({ ...recipes, recipes: [{ ...recipe, steps: ['Смешайте 80 г хлопьев.', 'Добавьте 100 г банана.'] }] })
  mount('/health/nutrition?recipe=oatmeal')
  const details = (await screen.findByText('Овсяная каша с бананом')).closest('details')!
  fireEvent.change(within(details).getByLabelText('Количество порций'), { target: { value: '3' } })
  fireEvent.click(within(details).getByRole('button', { name: 'Начать готовить' }))
  const dialog = screen.getByRole('dialog', { name: 'Готовим: Овсяная каша с бананом' })
  expect(within(dialog).getByText('Шаг 1 из 2')).toBeInTheDocument()
  expect(within(dialog).getByText('Смешайте 120 г хлопьев.')).toBeInTheDocument()
  expect(within(dialog).queryByText('Добавьте 150 г банана.')).not.toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('checkbox', { name: /Овсяные хлопья/ }))
  expect(within(dialog).getByRole('checkbox', { name: /Овсяные хлопья/ })).toBeChecked()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Далее' }))
  expect(within(dialog).getByText('Добавьте 150 г банана.')).toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Назад' }))
  expect(within(dialog).getByText('Шаг 1 из 2')).toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Закрыть режим готовки' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(details).toHaveAttribute('open')
  fireEvent.click(within(details).getByRole('button', { name: 'Начать готовить' }))
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('recipe library filters by meal and ingredient while keeping a deep linked recipe visible', async () => {
  const lunch = { ...recipe, id: 'chicken', name: 'Курица с рисом', meal: 'lunch', ingredients: [{ food_id: 'rice', grams: 90, state: 'dry' }] }
  const dinner = { ...recipe, id: 'salad', name: 'Овощной салат', meal: 'dinner', ingredients: [{ food_id: 'cucumber', grams: 150, state: 'raw' }] }
  apiMock.mockReset().mockResolvedValue({ ...recipes, foods: { ...recipes.foods, rice: { name: 'Рис', state: 'dry' }, cucumber: { name: 'Огурец', state: 'raw' } }, recipes: [recipe, lunch, dinner] })
  mount('/health/nutrition?recipe=chicken')
  const linked = (await screen.findByText('Курица с рисом')).closest('details')!
  expect(linked).toHaveAttribute('open')
  fireEvent.click(screen.getByRole('button', { name: 'Ужины (1)' }))
  expect(screen.getByText('Овощной салат')).toBeInTheDocument()
  expect(screen.queryByText('Курица с рисом')).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('searchbox', { name: 'Найти рецепт или продукт' }), { target: { value: 'рис' } })
  expect(screen.getByText('Ничего не найдено. Попробуйте другой приём пищи или запрос.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Все (3)' }))
  expect(screen.getByText('Курица с рисом')).toBeInTheDocument()
  expect(screen.queryByText('Овсяная каша с бананом')).not.toBeInTheDocument()
})

test('unsuitable recipe offers another compatible dish without the missing ingredient', async () => {
  const alternative = { ...recipe, id: 'eggs', name: 'Яйца с овощами', minutes: 8,
    ingredients: [{ food_id: 'egg', grams: 100, state: 'raw' }], allergens: ['egg'] }
  apiMock.mockReset().mockResolvedValue({ ...recipes, foods: { ...recipes.foods, egg: { name: 'Яйцо', state: 'raw' } }, recipes: [recipe, alternative] })
  mount('/health/nutrition?recipe=oatmeal')
  const details = (await screen.findByText('Овсяная каша с бананом')).closest('details')!
  fireEvent.click(within(details).getByRole('button', { name: 'Мне не подходит: Овсяная каша с бананом' }))
  fireEvent.change(within(details).getByLabelText('Почему не подходит Овсяная каша с бананом'), { target: { value: 'ingredient' } })
  fireEvent.change(within(details).getByLabelText('Какого продукта нет?'), { target: { value: 'банан' } })
  expect(within(details).getByRole('button', { name: 'Яйца с овощами' })).toBeInTheDocument()
  fireEvent.click(within(details).getByRole('button', { name: 'Яйца с овощами' }))
  await waitFor(() => expect(screen.getByText('Яйца с овощами', { selector: 'strong' }).closest('details')).toHaveAttribute('open'))
})

test('calculator calculates and keeps entered values after failed save', async () => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/nutrition/profile' && init?.method === 'PUT') throw new Error('Сохранение недоступно')
    if (path === '/health/nutrition/profile') return { profile: null }
    if (path === '/health/nutrition/estimate') return estimate
    throw new Error(`Unexpected ${path}`)
  })
  mount('/health/calories')
  fireEvent.change(screen.getByLabelText('Возраст'), { target: { value: '30' } })
  fireEvent.change(screen.getByLabelText('Рост, см'), { target: { value: '180' } })
  fireEvent.change(screen.getByLabelText('Вес, кг'), { target: { value: '80' } })
  fireEvent.change(screen.getByLabelText('Пол для расчёта'), { target: { value: 'male' } })
  fireEvent.change(screen.getByLabelText('Активность за день'), { target: { value: 'light' } })
  fireEvent.click(screen.getByRole('button', { name: 'Рассчитать калории' }))
  await screen.findByText('2451 ккал')
  expect(screen.getByText('Ориентир на день, ккал/день')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить расчёт' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Сохранение недоступно')
  expect(screen.getByLabelText('Возраст')).toHaveValue(30)
  expect(screen.queryByRole('heading', { name: 'Готовые рецепты' })).not.toBeInTheDocument()
})

test('calculator puts the goal and required inputs before one clear calculate action', async () => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/nutrition/profile') return { profile: null }
    if (path === '/health/nutrition/estimate' && init?.method === 'POST') return estimate
    throw new Error(`Unexpected ${path}`)
  })
  mount('/health/calories')
  await screen.findByRole('heading', { name: 'Калькулятор калорий' })
  expect(screen.getByRole('button', { name: 'Рассчитать калории' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Сохранить расчёт' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Возраст'), { target: { value: '30' } })
  fireEvent.change(screen.getByLabelText('Рост, см'), { target: { value: '180' } })
  fireEvent.change(screen.getByLabelText('Вес, кг'), { target: { value: '80' } })
  fireEvent.change(screen.getByLabelText('Пол для расчёта'), { target: { value: 'male' } })
  fireEvent.change(screen.getByLabelText('Цель'), { target: { value: 'gain' } })
  fireEvent.click(screen.getByRole('button', { name: 'Рассчитать калории' }))
  expect(screen.getByRole('alert')).toHaveTextContent('активность')
  expect(apiMock).not.toHaveBeenCalledWith('/health/nutrition/estimate', expect.anything())
  fireEvent.change(screen.getByLabelText('Активность за день'), { target: { value: 'light' } })
  fireEvent.click(screen.getByRole('button', { name: 'Рассчитать калории' }))
  await screen.findByText('2451 ккал')
  expect(screen.getByRole('button', { name: 'Сохранить расчёт' })).toBeInTheDocument()
  const call = apiMock.mock.calls.find(([path]) => path === '/health/nutrition/estimate')
  expect(JSON.parse(call?.[1]?.body as string)).toMatchObject({ age: 30, height_cm: 180, weight_kg: 80, formula_sex: 'male', goal: 'gain' })
})

test('calculator preserves saved preferences and accepts a logged weight link', async () => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/nutrition/profile' && init?.method === 'PUT') return { profile: { answers: { ...answers, weight_kg: 77.5 }, preferences, ...estimate } }
    if (path === '/health/nutrition/profile') return { profile: { answers, preferences, ...estimate } }
    if (path === '/health/nutrition/estimate') return estimate
    throw new Error(`Unexpected ${path}`)
  })
  mount('/health/calories?weight=77.5')
  await waitFor(() => expect(screen.getByLabelText('Вес, кг')).toHaveValue(77.5))
  fireEvent.click(screen.getByRole('button', { name: 'Рассчитать калории' }))
  await screen.findByText('2451 ккал')
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить расчёт' }))
  await screen.findByText('Расчёт сохранён.')
  const call = apiMock.mock.calls.find(([path, init]) => path === '/health/nutrition/profile' && init?.method === 'PUT')
  expect(JSON.parse(call?.[1]?.body as string)).toMatchObject({ answers: { weight_kg: 77.5 }, preferences })
})
