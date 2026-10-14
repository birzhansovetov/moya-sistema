import { scaleRecipeStep } from './recipeSteps'

test('scales ingredient grams in preparation without changing time or temperature', () => {
  expect(scaleRecipeStep('Смешайте 100 г риса и 5 г масла, запекайте при 180 °C 20 минут.', 1.5)).toBe('Смешайте 150 г риса и 7,5 г масла, запекайте при 180 °C 20 минут.')
})
