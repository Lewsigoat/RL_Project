import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { QuizMode, QuizQuestion } from '../lib/quiz.ts'
import { buildQuiz, gradeMultipleChoice, gradeTypeTerm } from '../lib/quiz.ts'
import { enabledChapters, enabledTerms, filterTermsByChapter } from '../lib/selectors.ts'
import { useAppState } from '../state/AppStateContext.tsx'
import styles from './Quiz.module.css'

export function Quiz() {
  const { state, catalog, today, quizAnswer, finishQuiz } = useAppState()
  const [mode, setMode] = useState<QuizMode>('multiple-choice')
  const [chapterId, setChapterId] = useState('all')
  const [count, setCount] = useState(10)
  const [questions, setQuestions] = useState<QuizQuestion[] | null>(null)
  const [index, setIndex] = useState(0)
  const [choice, setChoice] = useState<string | null>(null)
  const [typed, setTyped] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [checked, setChecked] = useState<boolean | null>(null)
  const [score, setScore] = useState({ correct: 0, total: 0 })

  const chapters = enabledChapters(catalog.chapters, state.enabledChapterIds)
  const pool = useMemo(() => {
    const enabled = enabledTerms(catalog.terms, state.enabledChapterIds)
    return filterTermsByChapter(enabled, chapterId === 'all' || state.enabledChapterIds.includes(chapterId) ? chapterId : 'all')
  }, [catalog.terms, chapterId, state.enabledChapterIds])

  const question = questions?.[index] ?? null

  function start() {
    const next = buildQuiz(mode, pool, count)
    setQuestions(next)
    setIndex(0)
    setChoice(null)
    setTyped('')
    setRevealed(false)
    setChecked(null)
    setScore({ correct: 0, total: 0 })
  }

  function mark(correct: boolean) {
    if (!question || !questions) return
    quizAnswer(question.term.id, correct)
    const nextScore = { correct: score.correct + (correct ? 1 : 0), total: score.total + 1 }
    setScore(nextScore)
    const nextIndex = index + 1
    if (nextIndex >= questions.length) {
      finishQuiz({ date: today, mode, correct: nextScore.correct, total: nextScore.total })
      setQuestions([])
      setChecked(null)
      return
    }
    setIndex(nextIndex)
    setChoice(null)
    setTyped('')
    setRevealed(false)
    setChecked(null)
  }

  if (chapters.length === 0) {
    return (
      <section className={styles.panel}>
        <h1>No chapters enabled</h1>
        <p>Quizzes only use terms from chapters you have turned on.</p>
        <Link className="button primary" to="/">
          Enable chapters
        </Link>
      </section>
    )
  }

  if (score.total > 0 && (!questions || questions.length === 0)) {
    return (
      <section className={styles.panel}>
        <p className={styles.kicker}>Quiz complete</p>
        <h1>
          {score.correct} / {score.total} correct
        </h1>
        <p>{score.correct === score.total ? 'Clean sweep. Those definitions are sticking.' : 'Misses land on your weak-terms list so you can restudy them.'}</p>
        <div className={styles.row}>
          <button type="button" className="button primary" onClick={start}>
            Quiz again
          </button>
          <button type="button" className="button" onClick={() => setScore({ correct: 0, total: 0 })}>
            Change settings
          </button>
        </div>
      </section>
    )
  }

  if (question) {
    return (
      <section className={styles.panel}>
        <div className={styles.progress}>
          Question {index + 1} / {questions?.length}
        </div>
        {question.mode === 'multiple-choice' ? (
          <>
            <p className={styles.prompt}>{question.prompt}</p>
            <div className={styles.options}>
              {question.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={choice === option ? `${styles.option} ${styles.selected}` : styles.option}
                  onClick={() => setChoice(option)}
                >
                  {option}
                </button>
              ))}
            </div>
            {checked === null ? (
              <button type="button" className="button primary" disabled={!choice} onClick={() => setChecked(gradeMultipleChoice(question, choice ?? ''))}>
                Check
              </button>
            ) : (
              <Feedback correct={checked} answer={question.answer} onNext={() => mark(checked)} />
            )}
          </>
        ) : null}
        {question.mode === 'type-term' ? (
          <>
            <p className={styles.prompt}>{question.prompt}</p>
            <form
              className={styles.form}
              onSubmit={(event) => {
                event.preventDefault()
                if (checked === null) setChecked(gradeTypeTerm(question, typed))
              }}
            >
              <input value={typed} onChange={(event) => setTyped(event.target.value)} placeholder="Type the term" autoFocus />
              {checked === null ? (
                <button type="submit" className="button primary" disabled={!typed.trim()}>
                  Check
                </button>
              ) : (
                <Feedback correct={checked} answer={question.term.term} onNext={() => mark(checked)} />
              )}
            </form>
          </>
        ) : null}
        {question.mode === 'explain' ? (
          <>
            <h1>{question.prompt}</h1>
            <p>Explain it in your head, then reveal the definition and grade yourself.</p>
            {revealed ? <p className={styles.reveal}>{question.reveal}</p> : (
              <button type="button" className="button" onClick={() => setRevealed(true)}>
                Reveal definition
              </button>
            )}
            {revealed ? (
              <div className={styles.row}>
                <button type="button" className="button primary" onClick={() => mark(true)}>
                  Knew it
                </button>
                <button type="button" className="button" onClick={() => mark(false)}>
                  Almost
                </button>
                <button type="button" className="button" onClick={() => mark(false)}>
                  Missed
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <p className={styles.kicker}>Quiz</p>
      <h1>Test only the chapters you enabled</h1>
      <p>{pool.length} unlocked terms are available.</p>
      <div className={styles.grid}>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as QuizMode)}>
            <option value="multiple-choice">Multiple choice</option>
            <option value="type-term">Type the term</option>
            <option value="explain">Explain it yourself</option>
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
        <label>
          Questions
          <input type="number" min={1} max={50} value={count} onChange={(event) => setCount(Number(event.target.value) || 1)} />
        </label>
      </div>
      <button type="button" className="button primary" onClick={start} disabled={pool.length === 0}>
        Start quiz
      </button>
    </section>
  )
}

function Feedback({ correct, answer, onNext }: { correct: boolean; answer: string; onNext: () => void }) {
  return (
    <div className={styles.feedback}>
      <p>{correct ? 'Correct.' : `Not quite. The term is “${answer}”.`}</p>
      <button type="button" className="button primary" onClick={onNext}>
        Next
      </button>
    </div>
  )
}
