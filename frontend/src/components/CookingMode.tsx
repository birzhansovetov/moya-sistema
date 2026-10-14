import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { Food, Recipe } from '../healthTypes'
import { scaleRecipeStep } from '../recipeSteps'

const number = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1).replace('.', ',')

export function CookingMode({ recipe, foods, portions, onClose }: { recipe: Recipe; foods: Record<string, Food>; portions: number; onClose: () => void }) {
  const [step, setStep] = useState(0)
  const [checked, setChecked] = useState<string[]>([])
  const closeRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const factor = portions / recipe.servings

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
      if (!items.length) return
      const first = items[0], last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.body.style.overflow = oldOverflow; document.removeEventListener('keydown', onKey); previous?.focus() }
  }, [onClose])

  return createPortal(<div className="cookingBackdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <div ref={dialogRef} className="cookingDialog" role="dialog" aria-modal="true" aria-label={`Готовим: ${recipe.name}`}>
      <header className="cookingHeader"><div><span className="cookingEyebrow">Режим готовки</span><h2>{recipe.name}</h2><p>{number(portions)} порц. · {recipe.minutes} мин</p></div><button ref={closeRef} type="button" className="cookingClose" onClick={onClose} aria-label="Закрыть режим готовки">×</button></header>
      <div className="cookingContent">
        <section className="cookingIngredients" aria-label="Ингредиенты"><h3>Ингредиенты</h3><p>{checked.length} из {recipe.ingredients.length} отмечено</p><ul>{recipe.ingredients.map(item => <li key={item.food_id}><label><input type="checkbox" checked={checked.includes(item.food_id)} onChange={() => setChecked(current => current.includes(item.food_id) ? current.filter(id => id !== item.food_id) : [...current, item.food_id])} /><span>{foods[item.food_id]?.name || item.food_name || item.food_id}</span><strong>{number(item.grams * factor)} г</strong></label></li>)}</ul></section>
        <section className="cookingStep" aria-live="polite"><p className="cookingEyebrow">Шаг {step + 1} из {recipe.steps.length}</p><p className="cookingInstruction">{scaleRecipeStep(recipe.steps[step], factor)}</p><div className="cookingProgress" aria-hidden="true"><span style={{ width: `${((step + 1) / recipe.steps.length) * 100}%` }} /></div><div className="cookingActions"><button type="button" onClick={() => setStep(current => current - 1)} disabled={step === 0}>Назад</button><button type="button" className="primaryButton" onClick={() => step === recipe.steps.length - 1 ? onClose() : setStep(current => current + 1)}>{step === recipe.steps.length - 1 ? 'Завершить' : 'Далее'}</button></div></section>
      </div>
    </div>
  </div>, document.body)
}
