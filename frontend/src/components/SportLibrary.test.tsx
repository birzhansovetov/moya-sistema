import {fireEvent,render,screen} from '@testing-library/react'
import {SportLibrary} from './SportLibrary'

const exercises={
  chair_squat:{name:'Приседание до стула',technique:'Коснитесь сиденья и встаньте.',common_errors:'Не падайте на стул.',easier_version:'Помогайте руками.',substitution:'Неглубокий присед.',source:'https://www.nhs.uk/live-well/exercise/strength-exercises/'},
  seated_row:{name:'Горизонтальная тяга в тренажёре',technique:'Потяните рукояти к корпусу.',common_errors:'Не дёргайте корпус.',easier_version:'Уменьшите вес.',substitution:'Тяга резинки.',source:'https://www.acefitness.org/resources/everyone/exercise-library/168/seated-row/'},
}

test('library makes techniques searchable and filters equipment without losing source',()=>{
  render(<SportLibrary exercises={exercises}/>)
  fireEvent.click(screen.getByText(/Библиотека упражнений/))
  expect(screen.getByText('2 упражнения')).toBeInTheDocument()
  fireEvent.change(screen.getByRole('searchbox',{name:'Найти упражнение'}),{target:{value:'тяга'}})
  expect(screen.getByText('Горизонтальная тяга в тренажёре')).toBeInTheDocument()
  expect(screen.queryByText('Приседание до стула')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('Горизонтальная тяга в тренажёре'))
  expect(screen.getByText('Потяните рукояти к корпусу.')).toBeInTheDocument()
  expect(screen.getByRole('link',{name:'Источник техники'})).toHaveAttribute('href',exercises.seated_row.source)
  fireEvent.change(screen.getByRole('searchbox',{name:'Найти упражнение'}),{target:{value:''}})
  fireEvent.click(screen.getByRole('button',{name:'Без оборудования'}))
  expect(screen.getByText('Приседание до стула')).toBeInTheDocument()
  expect(screen.queryByText('Горизонтальная тяга в тренажёре')).not.toBeInTheDocument()
})
