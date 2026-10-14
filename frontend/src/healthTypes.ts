export type NutritionAnswers = {
  age: number; height_cm: number; weight_kg: number; formula_sex: 'male' | 'female' | 'unspecified'
  activity: 'unspecified' | 'light' | 'moderate' | 'vigorous'; goal: 'fat_loss' | 'maintain' | 'gain'
  pregnant: boolean; breastfeeding: boolean; special_condition: boolean
}
export type NutritionPreferences = {
  vegetarian: boolean; allergies: Array<'gluten' | 'milk' | 'egg' | 'fish'>; excluded_food_ids: string[]
  budget: 'low' | 'any'; max_minutes: number
}
export type NutritionEstimate = {
  resting_kcal: number; maintenance_kcal: number; target_kcal: number
  protein_g: number; fat_g: number; carbs_g: number; explanation: string; limits: string
}
export type EstimateResponse = { estimate: NutritionEstimate | null; reasons: string[]; sources: Record<string, string> }
export type NutritionProfile = { answers: NutritionAnswers; preferences: NutritionPreferences; estimate: NutritionEstimate | null; reasons: string[]; sources: Record<string, string> }
export type Food = { name: string; state: 'raw' | 'dry' | 'as_packaged'; source_url: string; kcal?: number; protein_g?: number; fat_g?: number; carbs_g?: number }
export type Ingredient = { food_id: string; grams: number; state: Food['state']; food_name?: string; source_url?: string }
export type Nutrients = { kcal: number; protein_g: number; fat_g: number; carbs_g: number }
export type Recipe = { id: string; name: string; meal: 'breakfast' | 'lunch' | 'dinner'; minutes: number; servings: number; cost_tier: 'low' | 'medium'; vegetarian: boolean; allergens: string[]; ingredients: Ingredient[]; steps: string[]; source_url?: string; source_note?: string; nutrition_per_serving: Nutrients }
export type RecipeLibrary = { version: string; basis: string; foods: Record<string, Food>; recipes: Recipe[] }
export type MenuMeal = { meal: Recipe['meal']; recipe_id: string; portions: number; recipe: Recipe; nutrition: Nutrients }
export type MenuDay = { date: string; meals: MenuMeal[]; total: Nutrients; difference_kcal: number }
export type Menu = { id: string; start_date: string; target_kcal: number; stale: boolean; days: MenuDay[]; shopping_list: Array<{ food_id: string; name: string; state: Food['state']; unit: 'g'; quantity: number }> }
export type FoodLog = { id: string; date: string; recipe_id: string; recipe: Recipe; portions: number; nutrition: Nutrients }
export type WeightLog = { id: string; date: string; weight_kg: number }
export const mealNames = { breakfast: 'завтрак', lunch: 'обед', dinner: 'ужин' } as const
export const stateNames = { raw: 'сырой продукт', dry: 'сухой продукт', as_packaged: 'как в упаковке' } as const

export function isCalendarDate(value: string | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T12:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}
