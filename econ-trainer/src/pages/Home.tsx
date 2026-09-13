import { Link } from 'react-router-dom'
import { Meter } from '../components/Meter.tsx'
import { termsForChapter } from '../data/catalog.ts'
import { chapterMastery, dueCounts, enabledTerms } from '../lib/selectors.ts'
import { useAppState } from '../state/AppStateContext.tsx'
import styles from './Home.module.css'

export function Home() {
  const { state, catalog, today, enable, disable } = useAppState()
  const available = enabledTerms(catalog.terms, state.enabledChapterIds)
  const due = dueCounts(available, state.cards, today, Math.max(0, state.newCap - state.newToday))
  const goalRatio = Math.min(1, state.reviewsToday / state.dailyGoal)

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>Today</p>
          <h1>Enable a chapter, then learn its definitions.</h1>
          <p className={styles.lead}>
            42 Edexcel IGCSE (EC2) chapters, in your workbook wording. Locked chapters stay out of study,
            quizzes, and the glossary. Turn them on one by one when you are ready.
          </p>
        </div>
        <div className={styles.stats}>
          <div>
            <strong>{due.total}</strong>
            <span>due now</span>
          </div>
          <div>
            <strong>{due.review}</strong>
            <span>reviews due</span>
          </div>
          <div>
            <strong>{due.nextNew}</strong>
            <span>new left</span>
          </div>
          <div>
            <strong>{state.streak}</strong>
            <span>day streak</span>
          </div>
        </div>
        <Meter value={goalRatio} label={`${state.reviewsToday}/${state.dailyGoal} goal`} />
        <div className={styles.actions}>
          <Link className="button primary" to="/study">
            Start studying
          </Link>
          <Link className="button" to="/quiz">
            Take a quiz
          </Link>
        </div>
      </section>

      <div className={styles.toolbar}>
        <h2>Chapters</h2>
        <div className={styles.actions}>
          <button
            type="button"
            className="button"
            onClick={() => catalog.chapters.forEach((chapter) => enable(chapter.id))}
          >
            Enable all
          </button>
          <button
            type="button"
            className="button"
            onClick={() => catalog.chapters.forEach((chapter) => disable(chapter.id))}
          >
            Disable all
          </button>
        </div>
      </div>

      <ol className={styles.list}>
        {catalog.chapters.map((chapter) => {
          const on = state.enabledChapterIds.includes(chapter.id)
          const count = termsForChapter(catalog.terms, chapter.id).length
          const mastery = chapterMastery(catalog.terms, state.cards, chapter.id)
          return (
            <li key={chapter.id} className={on ? styles.cardOn : styles.card}>
              <label className={styles.switchRow}>
                <input
                  type="checkbox"
                  checked={on}
                  onChange={(event) => (event.target.checked ? enable(chapter.id) : disable(chapter.id))}
                />
                <span className={styles.number}>{chapter.number}</span>
                <span className={styles.body}>
                  <strong>{chapter.title}</strong>
                  <em>{chapter.summary}</em>
                  <span className={styles.meta}>
                    {count} terms
                    {on ? ` · ${mastery.seen} seen` : ' · locked'}
                  </span>
                  {on ? <Meter value={mastery.score} label={`${Math.round(mastery.score * 100)}%`} /> : null}
                </span>
              </label>
            </li>
          )
        })}
      </ol>

      {available.length === 0 ? (
        <p className={styles.empty}>
          Enable Chapter 1 to load its terms into the due queue. {termsForChapter(catalog.terms, 'ch1').length}{' '}
          definitions are waiting.
        </p>
      ) : null}
    </div>
  )
}
