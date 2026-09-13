import { NavLink, Outlet } from 'react-router-dom'
import styles from './Layout.module.css'
import { useAppState } from '../state/AppStateContext.tsx'
import { dueCounts, enabledTerms } from '../lib/selectors.ts'

const links = [
  { to: '/', label: 'Chapters', end: true },
  { to: '/study', label: 'Study' },
  { to: '/quiz', label: 'Quiz' },
  { to: '/glossary', label: 'Glossary' },
  { to: '/progress', label: 'Progress' },
]

export function Layout() {
  const { state, catalog, today } = useAppState()
  const available = enabledTerms(catalog.terms, state.enabledChapterIds)
  const due = dueCounts(available, state.cards, today, Math.max(0, state.newCap - state.newToday))

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">
            §
          </span>
          <div>
            <p className={styles.title}>Econ Trainer</p>
            <p className={styles.tag}>Learn definitions, one chapter at a time</p>
          </div>
        </div>
        <nav className={styles.nav} aria-label="Main">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => (isActive ? `${styles.link} ${styles.active}` : styles.link)}
            >
              {link.label}
              {link.to === '/study' && due.total > 0 ? <span className={styles.badge}>{due.total}</span> : null}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
