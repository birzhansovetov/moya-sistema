import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Button, Card, Dialog, Input, Select } from './ui'

describe('shared interface components', () => {
  it('keeps the action label and button size while loading', () => {
    render(<Button loading>Сохранить длинную запись тренировки</Button>)
    const button = screen.getByRole('button', { name: /Сохранить длинную запись тренировки/ })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveAttribute('aria-label', 'Сохранить длинную запись тренировки')
    expect(button).toHaveTextContent('Сохранить длинную запись тренировки')
  })

  it('connects a field error with its input and keeps a long label', () => {
    render(<Input label="Өзгерістерді сақтау үшін толық атауды енгізіңіз" error="Поле обязательно" />)
    const input = screen.getByRole('textbox', { name: 'Өзгерістерді сақтау үшін толық атауды енгізіңіз' })
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Поле обязательно')
  })

  it('renders a select and card with their content', () => {
    render(<Card><Select label="Место тренировки" options={[{ value: 'gym', label: 'В зале' }]} /></Card>)
    expect(screen.getByRole('combobox', { name: 'Место тренировки' })).toHaveValue('gym')
    expect(screen.getByText('В зале')).toBeInTheDocument()
  })

  it('closes a modal with escape and restores focus', () => {
    function Example() {
      const [open, setOpen] = useState(false)
      return <><button onClick={() => setOpen(true)}>Открыть</button><Dialog open={open} title="Изменить план" onClose={() => setOpen(false)}><button>Сохранить</button></Dialog></>
    }
    render(<Example />)
    const opener = screen.getByRole('button', { name: 'Открыть' })
    opener.focus()
    fireEvent.click(opener)
    expect(screen.getByRole('dialog', { name: 'Изменить план' })).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})
