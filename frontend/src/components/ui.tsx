import { useEffect, useId, useRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' | 'danger'; loading?: boolean }

export function Button({ variant = 'primary', loading = false, disabled, children, className = '', 'aria-label': ariaLabel, ...props }: ButtonProps) {
  return <button {...props} className={`uiButton uiButton--${variant} ${className}`.trim()} disabled={disabled || loading} aria-busy={loading || undefined} aria-label={ariaLabel || (loading && typeof children === 'string' ? children : undefined)}>
    <span className="uiButtonContent">{children}</span>{loading && <span className="uiButtonSpinner" aria-hidden="true" />}
  </button>
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }

export function Input({ label, error, hint, id, className = '', ...props }: InputProps) {
  const generatedId = useId()
  const fieldId = id || generatedId
  const descriptionId = error || hint ? `${fieldId}-description` : undefined
  return <div className={`uiField ${className}`.trim()}>
    <label className="uiFieldLabel" htmlFor={fieldId}>{label}</label>
    <input {...props} id={fieldId} className="uiInput" aria-invalid={!!error || undefined} aria-describedby={descriptionId} />
    <span id={descriptionId} className={error ? 'uiFieldError' : 'uiFieldHint'} role={error ? 'alert' : undefined} aria-hidden={!error && !hint}>{error || hint}</span>
  </div>
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> & { label: string; options: { value: string; label: string }[]; error?: string; hint?: string }

export function Select({ label, options, error, hint, id, className = '', ...props }: SelectProps) {
  const generatedId = useId()
  const fieldId = id || generatedId
  const descriptionId = error || hint ? `${fieldId}-description` : undefined
  return <div className={`uiField ${className}`.trim()}>
    <label className="uiFieldLabel" htmlFor={fieldId}>{label}</label>
    <select {...props} id={fieldId} className="uiSelect" aria-invalid={!!error || undefined} aria-describedby={descriptionId}>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
    <span id={descriptionId} className={error ? 'uiFieldError' : 'uiFieldHint'} role={error ? 'alert' : undefined} aria-hidden={!error && !hint}>{error || hint}</span>
  </div>
}

export function Card({ children, className = '', ...props }: HTMLAttributes<HTMLElement>) {
  return <section {...props} className={`card uiCard ${className}`.trim()}>{children}</section>
}

export function Dialog({ open, title, onClose, children, returnFocusTo, className = '' }: { open: boolean; title: string; onClose: () => void; children: ReactNode; returnFocusTo?: HTMLElement | null; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!open) return
    const dialog = ref.current
    if (!dialog) return
    opener.current = returnFocusTo || (document.activeElement as HTMLElement | null)
    if (typeof dialog.showModal === 'function') dialog.showModal()
    else dialog.setAttribute('open', '')
    ;(dialog.querySelector<HTMLElement>('input:not([type="hidden"])') || dialog.querySelector<HTMLElement>('select, textarea') || dialog.querySelector<HTMLElement>('button'))?.focus()
    return () => {
      if (dialog.open && typeof dialog.close === 'function') dialog.close()
      opener.current?.focus()
    }
  }, [open, returnFocusTo])
  if (!open) return null
  return <dialog ref={ref} aria-label={title} className={`uiDialog ${className}`.trim()} onCancel={event => { event.preventDefault(); onClose() }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); onClose() } }} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    {children}
  </dialog>
}
