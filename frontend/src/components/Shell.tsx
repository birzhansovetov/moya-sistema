import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import styles from './Shell.module.css'

type IconName = 'today' | 'sections' | 'tasks' | 'calendar' | 'profile'

function Icon({ name }: { name: IconName }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  return <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" {...common}>
    {name === 'today' && <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M8 12h8M12 8v8" /></>}
    {name === 'sections' && <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>}
    {name === 'tasks' && <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="m7.5 12 3 3 6-6" /></>}
    {name === 'calendar' && <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 10h18" /></>}
    {name === 'profile' && <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" /></>}
  </svg>
}

const links: { to: string; text: string; icon: IconName; end?: boolean }[] = [
  { to: '/', text: 'Мой день', icon: 'today', end: true },
  { to: '/sections', text: 'Разделы', icon: 'sections' },
  { to: '/tasks', text: 'Задачи', icon: 'tasks' },
  { to: '/calendar', text: 'Календарь', icon: 'calendar' },
]

const spherePaths = ['/health', '/education', '/profession', '/languages', '/finance', '/personal']
const sphereNames: Record<string, string> = { health: 'Здоровье', education: 'Обучение', profession: 'Профессия', languages: 'Языки', finance: 'Финансы', personal: 'Личное' }

export function themeForPath(pathname: string) {
  if (pathname === '/health/sport') return 'sport'
  if (pathname === '/health/nutrition') return 'nutrition'
  if (pathname === '/health/calories') return 'calories'
  if (pathname === '/education/java' || pathname === '/education/go') return 'study-code'
  if (pathname === '/profession') return 'profession'
  if (pathname === '/languages' || pathname.startsWith('/languages/')) return 'language'
  if (pathname === '/education/reading') return 'reading'
  if (pathname === '/finance') return 'finance'
  if (pathname === '/personal') return 'personal'
  return 'neutral'
}

export function Shell() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  useEffect(() => { document.documentElement.scrollTop = 0 }, [pathname])
  const theme = themeForPath(pathname)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    return () => { delete document.documentElement.dataset.theme }
  }, [theme])
  const sectionPage = spherePaths.some(path => pathname === path || pathname.startsWith(`${path}/`))
  const sphere = pathname.split('/')[1]
  const pageNames: Record<string, string> = { '/health/sport': 'Тренировки', '/health/nutrition': 'Рецепты', '/health/calories': 'Калории', '/education/reading': 'Книги', '/education/java': 'Java', '/education/go': 'Go' }
  const current = pageNames[pathname] || (pathname === '/' ? 'Мой день' : pathname === '/profile' ? 'Профиль' : pathname.startsWith('/tasks') ? 'Задачи' : pathname.startsWith('/calendar') ? 'Календарь' : sphereNames[sphere] || 'Разделы')
  const parent = pathname.startsWith('/health/') ? { to: '/health', label: 'здоровью' }
    : pathname.startsWith('/education/') ? { to: '/education', label: 'обучению' }
      : sectionPage ? { to: '/sections', label: 'разделам' } : null
  const navLink = (link: typeof links[number]) => {
    const active = link.to === '/' ? pathname === '/' : link.to === '/sections' ? pathname === '/sections' || sectionPage : pathname === link.to || pathname.startsWith(`${link.to}/`)
    return <Link key={link.to} to={link.to} aria-current={active ? 'page' : undefined} className={active ? `${styles.link} ${styles.active}` : styles.link}>
    <span className={styles.icon}><Icon name={link.icon} /></span><span>{link.text}</span>
    </Link>
  }
  return <div className={styles.layout} data-app-shell data-theme={theme}>
    <aside className={styles.sidebar}>
      <div className={styles.brand}><span className={styles.brandMark}>М</span><span>Моя система</span></div>
      <nav aria-label="Основная навигация">{links.map(navLink)}</nav>
      <div className={styles.spacer} />
      <NavLink to="/profile" className={({ isActive }) => isActive ? `${styles.profile} ${styles.active}` : styles.profile}>
        <span className={styles.avatar}>{(user?.name || user?.email || 'Я').slice(0, 1).toUpperCase()}</span>
        <span className={styles.profileText}><strong>{user?.name || 'Мой профиль'}</strong><small>{user?.email}</small></span>
        <Icon name="profile" />
      </NavLink>
    </aside>
    <div className={styles.mainArea}>
      <header className={styles.topbar}><div className={styles.location}><span className={styles.mobileBrand}>Моя система</span><span className={styles.desktopRoot}>{sectionPage ? 'Разделы' : 'Пространство'}</span><span className={styles.divider}>/</span><strong>{current}</strong></div><div className={styles.appHeader}>{parent ? <NavLink className={styles.backLink} to={parent.to} aria-label={`Назад к ${parent.label}`}>Назад</NavLink> : <span className={styles.appMark} aria-hidden="true">М</span>}<div className={styles.appTitle}><strong>{current}</strong></div><NavLink className={styles.headerProfile} to="/profile" aria-label="Открыть профиль"><Icon name="profile" /></NavLink></div></header>
      <main className={styles.content}><Outlet /></main>
    </div>
    <nav className={styles.mobileNav} aria-label="Мобильная навигация">
      {[...links, { to: '/profile', text: 'Профиль', icon: 'profile' as const }].map(navLink)}
    </nav>
  </div>
}
