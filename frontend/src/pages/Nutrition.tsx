import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, json } from '../api'
import { useAuth } from '../auth'
import type { EstimateResponse, NutritionAnswers, NutritionPreferences, NutritionProfile, Recipe, RecipeLibrary } from '../healthTypes'
import { mealNames, stateNames } from '../healthTypes'
import { scaleRecipeStep } from '../recipeSteps'
import { CookingMode } from '../components/CookingMode'
import { MaterialFit, type FitAlternative } from '../components/MaterialFit'
import { Button, Card, Input, Select } from '../components/ui'
import './Nutrition.css'

const initialAnswers: NutritionAnswers = { age: 0, height_cm: 0, weight_kg: 0, formula_sex: 'unspecified', activity: 'unspecified', goal: 'fat_loss', pregnant: false, breastfeeding: false, special_condition: false }
const initialPreferences: NutritionPreferences = { vegetarian: false, allergies: [], excluded_food_ids: [], budget: 'any', max_minutes: 45 }
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'Не удалось выполнить действие. Попробуйте ещё раз.'
const readable = (value: number) => Number.isInteger(value) ? `${value}` : value.toFixed(1)

export function NutritionPage({ view = 'nutrition' }: { view?: 'nutrition' | 'calculator' }) {
  return view === 'calculator' ? <CalorieCalculatorPage /> : <RecipePage />
}

function RecipePage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const selectedRecipe = params.get('recipe')
  const [meal, setMeal] = useState<'all' | Recipe['meal']>('all')
  const [search, setSearch] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [goalOverride, setGoalOverride] = useState<'fat_loss' | 'maintain' | 'gain' | null>(null)
  const onboarding = useQuery({ queryKey: ['onboarding', user?.id], queryFn: () => api<{ answers: { health: { vegetarian: boolean; max_cooking_minutes: number; nutrition_goal?: 'fat_loss' | 'maintain' | 'gain'; allergies?: string[] } } | null }>('/onboarding'), enabled: user?.onboarding_complete === true })
  const recipes = useQuery({ queryKey: ['nutrition-recipes'], queryFn: () => api<RecipeLibrary>('/health/nutrition/recipes') })
  const goal = goalOverride ?? onboarding.data?.answers?.health.nutrition_goal ?? 'maintain'
  const visible = recipes.data?.recipes.filter(recipe => {
    if (meal !== 'all' && recipe.meal !== meal) return false
    const preference = onboarding.data?.answers?.health
    if (preference?.allergies?.some(allergen => recipe.allergens.includes(allergen))) return false
    if (preference && !showAll && ((preference.vegetarian && !recipe.vegetarian) || recipe.minutes > preference.max_cooking_minutes)) return false
    const query = search.trim().toLocaleLowerCase('ru')
    return !query || [recipe.name, ...recipe.ingredients.map(item => recipes.data?.foods[item.food_id]?.name || item.food_name || '')].some(value => value.toLocaleLowerCase('ru').includes(query))
  }).sort((left, right) => goal === 'gain'
    ? (right.nutrition_per_serving.kcal + right.nutrition_per_serving.protein_g * 4) - (left.nutrition_per_serving.kcal + left.nutrition_per_serving.protein_g * 4)
    : goal === 'fat_loss'
      ? right.nutrition_per_serving.protein_g / Math.max(right.nutrition_per_serving.kcal, 1) - left.nutrition_per_serving.protein_g / Math.max(left.nutrition_per_serving.kcal, 1)
      : 0) || []
  function alternativesFor(recipe: Recipe): FitAlternative[] {
    const preference = onboarding.data?.answers?.health
    return (recipes.data?.recipes || []).filter(candidate => candidate.id !== recipe.id && candidate.meal === recipe.meal
      && !preference?.allergies?.some(allergen => candidate.allergens.includes(allergen))
      && (!preference?.vegetarian || candidate.vegetarian)
      && (!preference || candidate.minutes <= preference.max_cooking_minutes)).map(candidate => ({
      id: candidate.id, title: candidate.name, minutes: candidate.minutes, easier: candidate.steps.length < recipe.steps.length,
      detail: `${candidate.minutes} мин · ${readable(candidate.nutrition_per_serving.kcal)} ккал`,
      ingredients: candidate.ingredients.map(item => recipes.data?.foods[item.food_id]?.name || item.food_name || item.food_id),
      onSelect: () => { setSearch(''); setMeal(candidate.meal); setParams({ recipe: candidate.id }) },
    }))
  }
  return <div className="healthPage nutritionPage">
    <div className="pageHeader"><div><span className="eyebrow">ЗДОРОВЬЕ · РЕЦЕПТЫ</span><h1>Питание</h1><p>Готовые рецепты с точным количеством продуктов. Укажите порции, чтобы пересчитать граммы.</p></div><Link className="secondaryButton" to="/health">К здоровью</Link></div>
    {recipes.isLoading && <p className="muted">Загружаем рецепты…</p>}
    {recipes.isError && <p role="alert" className="errorMessage">Не удалось загрузить рецепты. <button className="textButton" onClick={() => void recipes.refetch()}>Повторить</button></p>}
    {recipes.data && <><div className="nutritionDiscovery"><Input className="nutritionSearch" label="Найти рецепт или продукт" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Например, рис или курица" /><div className="nutritionMealFilter" aria-label="Приём пищи">{(['all', 'breakfast', 'lunch', 'dinner'] as const).map(value => <button key={value} type="button" aria-pressed={meal === value} onClick={() => setMeal(value)}>{value === 'all' ? 'Все' : value === 'breakfast' ? 'Завтраки' : value === 'lunch' ? 'Обеды' : 'Ужины'} ({value === 'all' ? recipes.data.recipes.length : recipes.data.recipes.filter(recipe => recipe.meal === value).length})</button>)}</div></div><div className="nutritionGoalRow"><Select label="Показывать сначала" value={goal} onChange={event => setGoalOverride(event.target.value as 'fat_loss' | 'maintain' | 'gain')} options={[{value:'maintain',label:'Повседневные блюда'},{value:'fat_loss',label:'Для снижения веса'},{value:'gain',label:'Для набора массы'}]} hint={goal === 'gain' ? 'Выше блюда с большей калорийностью и белком. Количество порций выбираете вы.' : goal === 'fat_loss' ? 'Выше блюда с большим количеством белка относительно калорийности.' : 'Все подходящие рецепты без сортировки по цели.'} /></div>{onboarding.data?.answers && <label className="inlineCheck"><input type="checkbox" checked={showAll} onChange={event => setShowAll(event.target.checked)} />Показать блюда вне предпочтений по времени и вегетарианству; аллергены остаются исключены</label>}{visible.length ? <div className="nutritionRecipes">{visible.map(recipe => <RecipeCard key={recipe.id} recipe={recipe} library={recipes.data} initiallyOpen={recipe.id === selectedRecipe} alternatives={alternativesFor(recipe)} />)}</div> : <p className="card nutritionNoResults">{onboarding.data?.answers ? "Под ваши настройки рецептов не найдено. Попробуйте другой поиск или измените предпочтения." : "Ничего не найдено. Попробуйте другой приём пищи или запрос."}</p>}<p className="muted nutritionBasis">{recipes.data.basis}</p></>}
  </div>
}

function RecipeCard({ recipe, library, initiallyOpen, alternatives }: { recipe: Recipe; library: RecipeLibrary; initiallyOpen: boolean; alternatives: FitAlternative[] }) {
  const detailsRef = useRef<HTMLDetailsElement>(null)
  const [portions, setPortions] = useState(recipe.servings)
  const [cooking, setCooking] = useState(false)
  useEffect(() => { if (initiallyOpen) detailsRef.current?.setAttribute('open', '') }, [initiallyOpen])
  const factor = portions / recipe.servings
  const totalGrams = recipe.ingredients.reduce((sum, item) => sum + item.grams * factor, 0)
  return <details ref={detailsRef} className="card nutritionRecipe" id={`recipe-${recipe.id}`}>
    <summary><span className="nutritionRecipeHeading"><strong>{recipe.name}</strong><small>{mealNames[recipe.meal]} · {recipe.minutes} мин · {readable(recipe.nutrition_per_serving.kcal)} ккал на порцию</small></span><span className="nutritionRecipeOpen"><span className="nutritionRecipeOpenText">Открыть рецепт</span><span className="nutritionRecipeCloseText">Свернуть рецепт</span></span></summary>
    <div className="nutritionRecipeBody">
      <label className="nutritionPortions">Количество порций<input type="number" min="0.5" max="10" step="0.5" value={portions} onChange={event => { const value = Number(event.target.value); if (Number.isFinite(value) && value >= 0.5 && value <= 10) setPortions(value) }} /></label>
      <p className="nutritionRecipeTotal">Продукты: {readable(totalGrams)} г на {readable(portions)} порц.</p>
      <h3>Ингредиенты</h3>
      <ul className="nutritionIngredients">{recipe.ingredients.map(item => <li key={item.food_id}><span>{library.foods[item.food_id]?.name || item.food_name || item.food_id}<small>{stateNames[item.state]}</small></span><strong>{readable(item.grams * factor)} г</strong></li>)}</ul>
      <h3>Как приготовить</h3><ol className="healthList">{recipe.steps.map(step => <li key={step}>{scaleRecipeStep(step, factor)}</li>)}</ol>
      <Button type="button" variant="secondary" className="cookingStart" onClick={() => setCooking(true)}>Начать готовить</Button>
      {cooking && <CookingMode recipe={recipe} foods={library.foods} portions={portions} onClose={() => setCooking(false)} />}
      {recipe.source_url && <p className="muted nutritionRecipeSource">{recipe.source_note && <span>{recipe.source_note} </span>}<a href={recipe.source_url} target="_blank" rel="noreferrer">Исходная идея рецепта</a></p>}
      <p className="muted">На одну порцию: белки {readable(recipe.nutrition_per_serving.protein_g)} г · жиры {readable(recipe.nutrition_per_serving.fat_g)} г · углеводы {readable(recipe.nutrition_per_serving.carbs_g)} г.</p>
      <MaterialFit title={recipe.name} minutes={recipe.minutes} alternatives={alternatives} configureTo="/onboarding" reasons={['other', 'time', 'ingredient', 'goal']} />
    </div>
  </details>
}

function CalorieCalculatorPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const requestedWeight = params.get('weight')
  const client = useQueryClient()
  const profileKey = ['nutrition-profile', user?.id]
  const profile = useQuery({ queryKey: profileKey, queryFn: () => api<{ profile: NutritionProfile | null }>('/health/nutrition/profile') })
  const [answers, setAnswers] = useState<NutritionAnswers>(initialAnswers)
  const [preferences, setPreferences] = useState<NutritionPreferences>(initialPreferences)
  const [initialized, setInitialized] = useState(false)
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (initialized || !profile.data) return
    if (profile.data.profile) {
      setAnswers({ ...profile.data.profile.answers, ...(validWeight(requestedWeight) ? { weight_kg: Number(requestedWeight) } : {}) })
      setPreferences(profile.data.profile.preferences)
      if (!validWeight(requestedWeight)) setEstimate({ estimate: profile.data.profile.estimate, reasons: profile.data.profile.reasons, sources: profile.data.profile.sources })
    } else if (validWeight(requestedWeight)) setAnswers(current => ({ ...current, weight_kg: Number(requestedWeight) }))
    setInitialized(true)
  }, [initialized, profile.data, requestedWeight])

  const calculate = useMutation({ mutationFn: () => api<EstimateResponse>('/health/nutrition/estimate', json('POST', answers)), onSuccess: result => { setEstimate(result); setError(''); setNotice('') }, onError: cause => setError(errorText(cause)) })
  const save = useMutation({ mutationFn: () => api<{ profile: NutritionProfile }>('/health/nutrition/profile', json('PUT', { answers, preferences })), onSuccess: result => { client.setQueryData(profileKey, result); setEstimate({ estimate: result.profile.estimate, reasons: result.profile.reasons, sources: result.profile.sources }); setError(''); setNotice('Расчёт сохранён.') }, onError: cause => setError(errorText(cause)) })
  function update<K extends keyof NutritionAnswers>(key: K, value: NutritionAnswers[K]) { setAnswers(current => ({ ...current, [key]: value })); setEstimate(null); setNotice('') }
  function validate() { if (answers.age < 1 || answers.height_cm < 100 || answers.weight_kg < 25 || answers.formula_sex === 'unspecified' || answers.activity === 'unspecified') { setError('Укажите возраст, рост, вес, пол и активность для расчёта.'); return false } setError(''); return true }
  return <div className="healthPage nutritionCalculatorLayout">
    <div className="pageHeader"><div><span className="eyebrow">ЗДОРОВЬЕ · РАСЧЁТ</span><h1>Калькулятор калорий</h1><p>Укажите свои данные и цель — покажем ориентир калорий на день для похудения, поддержания или набора веса.</p></div><Link className="secondaryButton" to="/health">К здоровью</Link></div>
    {error && <p role="alert" className="errorMessage">{error}</p>}{notice && <p role="status" className="successMessage">{notice}</p>}
    {profile.isError && <p role="alert" className="errorMessage">Не удалось загрузить сохранённые данные. <button className="textButton" onClick={() => void profile.refetch()}>Повторить</button></p>}
    <div className="healthContent"><Card className="calorieForm"><h2>Ваши данные</h2><div className="formStack">
      <div className="formGrid"><label>Рост, см<input type="number" min="100" max="230" value={answers.height_cm || ''} onChange={event => update('height_cm', Number(event.target.value))} /></label><label>Вес, кг<input type="number" min="25" max="350" step="0.1" value={answers.weight_kg || ''} onChange={event => update('weight_kg', Number(event.target.value))} /></label></div>
      <div className="formGrid"><label>Пол для расчёта<select value={answers.formula_sex} onChange={event => update('formula_sex', event.target.value as NutritionAnswers['formula_sex'])}><option value="unspecified">Выберите</option><option value="male">Мужской</option><option value="female">Женский</option></select></label><label>Возраст<input type="number" min="1" max="120" value={answers.age || ''} onChange={event => update('age', Number(event.target.value))} /></label></div>
      <div className="formGrid"><label>Цель<select value={answers.goal} onChange={event => update('goal', event.target.value as NutritionAnswers['goal'])}><option value="fat_loss">Похудеть</option><option value="maintain">Поддерживать вес</option><option value="gain">Набрать вес</option></select></label><label>Активность за день<select value={answers.activity} onChange={event => update('activity', event.target.value as NutritionAnswers['activity'])}><option value="unspecified">Выберите</option><option value="light">Небольшая</option><option value="moderate">Умеренная</option><option value="vigorous">Высокая</option></select></label></div>
      <p className="muted">Возраст и активность влияют на расчёт. Выбирайте активность за весь день, включая работу и прогулки.</p>
      <details className="calorieConditions"><summary>Состояния, при которых обычный расчёт может не подойти</summary><div className="formStack"><label className="inlineCheck"><input type="checkbox" checked={answers.pregnant} onChange={event => update('pregnant', event.target.checked)} />Беременность</label><label className="inlineCheck"><input type="checkbox" checked={answers.breastfeeding} onChange={event => update('breastfeeding', event.target.checked)} />Грудное вскармливание</label><label className="inlineCheck"><input type="checkbox" checked={answers.special_condition} onChange={event => update('special_condition', event.target.checked)} />Есть состояние, влияющее на питание или обмен веществ</label></div></details>
      <Button className="calorieCalculate" loading={calculate.isPending} onClick={() => { if (validate()) calculate.mutate() }}>Рассчитать калории</Button>
    </div></Card>
    {estimate && <section className="card calorieResult"><h2>{answers.goal === 'fat_loss' ? 'Для похудения' : answers.goal === 'gain' ? 'Для набора веса' : 'Для поддержания веса'}</h2>{estimate.estimate ? <><p className="muted">Ориентир на день</p><strong className="healthHeroNumber">{estimate.estimate.target_kcal} ккал</strong><p>Для поддержания текущего веса: {estimate.estimate.maintenance_kcal} ккал/день.</p><p>Белки {estimate.estimate.protein_g} г · жиры {estimate.estimate.fat_g} г · углеводы {estimate.estimate.carbs_g} г</p><button className="secondaryButton" disabled={save.isPending} onClick={() => { if (validate()) save.mutate() }}>Сохранить расчёт</button><details className="calorieMethod"><summary>Как получено число</summary><p>Расход в покое: {estimate.estimate.resting_kcal} ккал.</p><p>{estimate.estimate.explanation}</p><p className="muted">{estimate.estimate.limits}</p></details></> : <><h3>Готового расчёта нет</h3>{estimate.reasons.map(reason => <p key={reason}>{reason}</p>)}</>}{Object.entries(estimate.sources).map(([key, url]) => <a className="healthSource" key={key} href={url} target="_blank" rel="noreferrer">Источник: {key}</a>)}</section>}
    </div>
  </div>
}

function validWeight(value: string | null) { const number = Number(value); return value !== null && Number.isFinite(number) && number >= 25 && number <= 350 }
