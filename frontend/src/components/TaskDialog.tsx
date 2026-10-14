import { type ReactNode } from 'react'
import { Dialog } from './ui'

export function TaskDialog({ children, onClose, label, returnFocusTo }: { children: ReactNode; onClose: () => void; label: string; returnFocusTo: HTMLElement | null }) {
  return <Dialog open title={label} onClose={onClose} returnFocusTo={returnFocusTo}>{children}</Dialog>
}
