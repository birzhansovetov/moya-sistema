import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { MaterialFit } from './MaterialFit'

test('a time constraint offers only shorter existing materials and keeps the original', () => {
  render(<MemoryRouter><MaterialFit title="Урок 2" minutes={45} configureTo="/onboarding"
    alternatives={[{ id: 'a', title: 'Короткий урок', minutes: 20, to: '/education/go?lesson=a' },
      { id: 'b', title: 'Длинный урок', minutes: 60, to: '/education/go?lesson=b' }]} /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Мне не подходит: Урок 2' }))
  fireEvent.change(screen.getByLabelText('Почему не подходит Урок 2'), { target: { value: 'time' } })
  expect(screen.getByRole('link', { name: 'Короткий урок' })).toHaveAttribute('href', '/education/go?lesson=a')
  expect(screen.queryByRole('link', { name: 'Длинный урок' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Изменить условия подбора' })).toHaveAttribute('href', '/onboarding')
})

test('unavailable alternative is stated honestly', () => {
  render(<MemoryRouter><MaterialFit title="Программа" configureTo="/health/sport#sport-form" alternatives={[]} /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Мне не подходит: Программа' }))
  expect(screen.getByText('Подходящей замены среди текущих материалов нет. Измените условия подбора.')).toBeInTheDocument()
})
