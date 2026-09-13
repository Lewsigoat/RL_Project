import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { enabledChapters, enabledTerms, filterTermsByChapter, buildStudyQueue, dueCounts } from '../lib/selectors.ts'
import type { StudyMode } from '../lib/selectors.ts'
import type { Rating } from '../lib/srs.ts'
import { useAppState } from '../state/AppStateContext.tsx'
import type { Term } from '../data/types.ts'
import styles from './Study.module.css'

type Direction = 'term-to-definition' | 'definition-to-term'

const ratings: { id: Rating; label: string; hint: string }[] = [
  { id: 'again', label: 'Again', hint: '1' },
  { id: 'hard', label: 'Hard', hint: '2' },
  { id: 'good', label: 'Good', hint: '3' },
  { id: 'easy', label: 'Easy', hint: '4' },
]

export function Study() {
  const { state, catalog, today, review } = useAppState()
  const [direction, setDirection] = useState<Direction>('term-to-definition')
  const [mode, setMode] = useState<StudyMode>('mixed')
  const [chapterId, setChapterId] = useState<string>('all')
  const [shuffleQueue, setShuffleQueue] = useState(true)
  const [queue, setQueue] = useState<Term[] | null>(null)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState<{ again: number; hard: number; good: number; easy: number } | null>(null)

  const chapters = enabledChapters(catalog.chapters, state.enabledChapterIds)
  const available = useMemo(() => {
    const enabled = enabledTerms(catalog.terms, state.enabledChapterIds)
    return filterTermsByChapter(enabled, chapterId === 'all' || state.enabledChapterIds.includes(chapterId) ? chapterId : 'all')
  }, [catalog.terms, chapterId, state.enabledChapterIds])
  const due = dueCounts(available, state.cards, today, Math.max(0, state.newCap - state.newToday))

  const card = queue?.[index] ?? null

  function start() {
    const next = buildStudyQueue({
      terms: available,
      cards: state.cards,
      today,
      newCapRemaining: Math.max(0, state.newCap - state.newToday),
      mode,
      shuffleQueue,
    })
    setQueue(next)
    setIndex(0)
    setFlipped(false)
    setDone(null)
  }

  function rate(rating: Rating) {
    if (!card || !queue) return
    review(card.id, rating)
    const nextIndex = index + 1
    setDone((current) => {
      const tally = current ?? { again: 0, hard: 0, good: 0, easy: 0 }
      return { ...tally, [rating]: tally[rating] + 1 }
    })
    if (nextIndex >= queue.length) {
      setQueue([])
      setIndex(0)
      setFlipped(false)
      return
    }
    setIndex(nextIndex)
    setFlipped(false)
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!queue) return
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) {
        return
      }
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault()
        if (!flipped) setFlipped(true)
        else if (card) rate('good')
      }
      if (!flipped) return
      if (event.key === '1') rate('again')
      if (event.key === '2') rate('hard')
      if (event.key === '3') rate('good')
      if (event.key === '4') rate('easy')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (chapters.length === 0) {
    return (
      <Empty
        title="No chapters enabled"
        body="Turn on Chapter 1 from the home screen to start a study queue."
      />
    )
  }

  if (done && (!queue || queue.length === 0)) {
    const total = done.again + done.hard + done.good + done.easy
    return (
      <section className={styles.panel}>
        <p className={styles.kicker}>Session complete</p>
        <h1>Nice work.</h1>
        <p>
          You rated {total} card{total === 1 ? '' : 's'}: {done.good} good, {done.easy} easy, {done.hard} hard,{' '}
          {done.again} again.
        </p>
        <div className={styles.row}>
          <button type="button" className="button primary" onClick={start}>
            Study more
          </button>
          <button type="button" className="button" onClick={() => setDone(null)}>
            Change settings
          </button>
          <Link className="button" to="/progress">
            See progress
          </Link>
        </div>
      </section>
    )
  }

  if (queue && card) {
    const front = direction === 'term-to-definition' ? card.term : card.definition
    const back = direction === 'term-to-definition' ? card.definition : card.term
    return (
      <section className={styles.session}>
        <div className={styles.progress}>
          <span>
            {index + 1} / {queue.length}
          </span>
          <button type="button" className="button" onClick={() => setQueue(null)}>
            End
          </button>
        </div>
        <button type="button" className={styles.card} onClick={() => setFlipped((value) => !value)}>
          <span className={styles.side}>{flipped ? 'Answer' : 'Prompt'}</span>
          <strong>{front}</strong>
          {flipped ? (
            <>
              <p>{back}</p>
              {card.example ? <em>{card.example}</em> : null}
            </>
          ) : (
            <p className={styles.hint}>Click or press space to flip</p>
          )}
        </button>
        {flipped ? (
          <div className={styles.ratings}>
            {ratings.map((item) => (
              <button key={item.id} type="button" className={`${styles.rate} ${styles[item.id]}`} onClick={() => rate(item.id)}>
                <kbd>{item.hint}</kbd>
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <p className={styles.kicker}>Study</p>
      <h1>Flashcards with spaced repetition</h1>
      <p>
        {due.review} reviews and {due.nextNew} new cards are ready from enabled chapters. Space flips; 1–4 rate
        the card.
      </p>
      <div className={styles.grid}>
        <label>
          Direction
          <select value={direction} onChange={(event) => setDirection(event.target.value as Direction)}>
            <option value="term-to-definition">Term → definition</option>
            <option value="definition-to-term">Definition → term</option>
          </select>
        </label>
        <label>
          Queue
          <select value={mode} onChange={(event) => setMode(event.target.value as StudyMode)}>
            <option value="mixed">Reviews first, then new</option>
            <option value="review">Reviews only</option>
            <option value="new">New cards only</option>
          </select>
        </label>
        <label>
          Chapter
          <select value={chapterId} onChange={(event) => setChapterId(event.target.value)}>
            <option value="all">All enabled chapters</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {chapter.number}. {chapter.title}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.check}>
          <input type="checkbox" checked={shuffleQueue} onChange={(event) => setShuffleQueue(event.target.checked)} />
          Shuffle the queue
        </label>
      </div>
      <div className={styles.row}>
        <button type="button" className="button primary" onClick={start} disabled={due.total === 0 && mode !== 'new' && due.nextNew === 0}>
          Start {due.total} cards
        </button>
        {due.total === 0 ? <span className={styles.muted}>Nothing is due. Enable another chapter or come back tomorrow.</span> : null}
      </div>
    </section>
  )
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <section className={styles.panel}>
      <h1>{title}</h1>
      <p>{body}</p>
      <Link className="button primary" to="/">
        Enable chapters
      </Link>
    </section>
  )
}
