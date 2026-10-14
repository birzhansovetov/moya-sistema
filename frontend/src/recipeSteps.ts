export function scaleRecipeStep(step: string, factor: number): string {
  return step.replace(/(\d+(?:[.,]\d+)?)\s*г(?![а-яё])/gi, (_, amount: string) => {
    const scaled = Number(amount.replace(',', '.')) * factor
    return `${Number(scaled.toFixed(1)).toLocaleString('ru-RU')} г`
  })
}
