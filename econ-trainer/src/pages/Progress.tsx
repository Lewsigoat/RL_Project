import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { isCatalog, termsForChapter } from '../data/catalog.ts'
import { Meter } from '../components/Meter.tsx'
import { chapterMastery, enabledTerms, weakTerms } from '../lib/selectors.ts'
import { exportPayload, readCustomCatalog } from '../lib/storage.ts'
import { useAppState } from '../state/AppStateContext.tsx'
import styles from './Progress.module.css'

export function Progress() {
  const { state, catalog, importBackup, resetProgress, replaceCustomCatalog, setDailyGoal, setNewCap } = useAppState()
  const backupRef = useRef<HTMLInputElement>(null)
  const packRef = useRef<HTMLInputElement>(null)
  const available = enabledTerms(catalog.terms, state.enabledChapterIds)
  const weak = weakTerms(available, state.cards)
  const recentQuizzes = [...state.quizHistory].slice(-5).reverse()

  function downloadBackup() {
    const blob = new Blob([exportPayload(state, readCustomCatalog())], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'econ-trainer-progress.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  async function onFile(file: File | undefined, kind: 'backup' | 'pack') {
    if (!file) return
    try {
      const parsed: unknown = JSON.parse(await file.text())
      if (kind === 'backup') {
        if (!importBackup(parsed)) window.alert('That file is not a valid Econ Trainer backup.')
        return
      }
      if (!isCatalog(parsed)) {
        window.alert('A term pack needs { "chapters": [], "terms": [] }.')
        return
      }
      replaceCustomCatalog(parsed)
    } catch {
      window.alert('Could not read that JSON file.')
    }
  }

  return (
    <div className={styles.page}>
      <section className={styles.panel}>
        <p className={styles.kicker}>Progress</p>
        <h1>How the unlocked chapters are sticking</h1>
        <div className={styles.stats}>
          <div>
            <strong>{state.streak}</strong>
            <span>day streak</span>
          </div>
          <div>
            <strong>{state.reviewsToday}</strong>
            <span>reviews today</span>
          </div>
          <div>
            <strong>{available.length}</strong>
            <span>unlocked terms</span>
          </div>
          <div>
            <strong>{weak.length}</strong>
            <span>weak terms</span>
          </div>
        </div>
      </section>

      <section className={styles.panel}>
        <h2>Chapter mastery</h2>
        <ul className={styles.mastery}>
          {catalog.chapters.map((chapter) => {
            const on = state.enabledChapterIds.includes(chapter.id)
            const mastery = chapterMastery(catalog.terms, state.cards, chapter.id)
            return (
              <li key={chapter.id} className={on ? undefined : styles.locked}>
                <div>
                  <strong>
                    {chapter.number}. {chapter.title}
                  </strong>
                  <span>
                    {on
                      ? `${mastery.seen}/${termsForChapter(catalog.terms, chapter.id).length} seen`
                      : 'locked'}
                  </span>
                </div>
                <Meter value={on ? mastery.score : 0} label={`${Math.round((on ? mastery.score : 0) * 100)}%`} />
              </li>
            )
          })}
        </ul>
      </section>

      <section className={styles.panel}>
        <h2>Weak terms</h2>
        {weak.length === 0 ? (
          <p className={styles.muted}>No struggling cards yet. Misses from study and quizzes will show up here.</p>
        ) : (
          <ul className={styles.weak}>
            {weak.slice(0, 12).map((term) => (
              <li key={term.id}>
                <Link to={`/glossary?term=${term.id}`}>{term.term}</Link>
                <span>{term.definition}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.panel}>
        <h2>Recent quizzes</h2>
        {recentQuizzes.length === 0 ? (
          <p className={styles.muted}>No quizzes yet.</p>
        ) : (
          <ul className={styles.quizzes}>
            {recentQuizzes.map((entry, index) => (
              <li key={`${entry.date}-${index}`}>
                {entry.date} · {entry.mode.replace('-', ' ')} · {entry.correct}/{entry.total}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.panel}>
        <h2>Session settings</h2>
        <div className={styles.settings}>
          <label>
            Daily review goal
            <input type="number" min={1} max={200} value={state.dailyGoal} onChange={(event) => setDailyGoal(Number(event.target.value) || 1)} />
          </label>
          <label>
            New cards per day
            <input type="number" min={0} max={100} value={state.newCap} onChange={(event) => setNewCap(Number(event.target.value) || 0)} />
          </label>
        </div>
      </section>

      <section className={styles.panel}>
        <h2>Backup and your own notes</h2>
        <p>
          Export keeps enabled chapters, card schedules, and any imported term pack. You can also drop in a JSON
          pack later if you want to add extra terms on top of the EC2 workbook bank.
        </p>
        <div className={styles.row}>
          <button type="button" className="button primary" onClick={downloadBackup}>
            Export progress
          </button>
          <button type="button" className="button" onClick={() => backupRef.current?.click()}>
            Import progress
          </button>
          <button type="button" className="button" onClick={() => packRef.current?.click()}>
            Import term pack
          </button>
          <button type="button" className="button" onClick={() => replaceCustomCatalog(null)}>
            Clear imported pack
          </button>
          <button
            type="button"
            className="button"
            onClick={() => {
              if (window.confirm('Reset streaks, reviews, and quiz history? Enabled chapters stay on.')) resetProgress()
            }}
          >
            Reset progress
          </button>
        </div>
        <input ref={backupRef} className={styles.hidden} type="file" accept="application/json" onChange={(event) => void onFile(event.target.files?.[0], 'backup')} />
        <input ref={packRef} className={styles.hidden} type="file" accept="application/json" onChange={(event) => void onFile(event.target.files?.[0], 'pack')} />
      </section>
    </div>
  )
}
