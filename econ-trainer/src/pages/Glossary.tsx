import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { chaptersById, termsById } from '../data/catalog.ts'
import { enabledChapters, enabledTerms, filterTermsByChapter, searchTerms } from '../lib/selectors.ts'
import { useAppState } from '../state/AppStateContext.tsx'
import styles from './Glossary.module.css'

export function Glossary() {
  const { state, catalog } = useAppState()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') ?? '')
  const selected = params.get('term')
  const chapterId = params.get('chapter') ?? 'all'

  const chapters = enabledChapters(catalog.chapters, state.enabledChapterIds)
  const chapterMap = chaptersById(catalog.chapters)
  const termMap = termsById(catalog.terms)
  const enabled = enabledTerms(catalog.terms, state.enabledChapterIds)
  const visible = useMemo(() => {
    return searchTerms(filterTermsByChapter(enabled, chapterId), query)
  }, [chapterId, enabled, query])

  if (chapters.length === 0) {
    return (
      <section className={styles.panel}>
        <h1>Glossary is empty</h1>
        <p>Enable a chapter to browse its definitions.</p>
        <Link className="button primary" to="/">
          Enable chapters
        </Link>
      </section>
    )
  }

  return (
    <div className={styles.page}>
      <section className={styles.panel}>
        <p className={styles.kicker}>Glossary</p>
        <h1>Search the chapters you unlocked</h1>
        <div className={styles.filters}>
          <input
            value={query}
            placeholder="Search terms, definitions, examples"
            onChange={(event) => {
              setQuery(event.target.value)
              const next = new URLSearchParams(params)
              if (event.target.value) next.set('q', event.target.value)
              else next.delete('q')
              setParams(next, { replace: true })
            }}
          />
          <select
            value={chapterId}
            onChange={(event) => {
              const next = new URLSearchParams(params)
              if (event.target.value === 'all') next.delete('chapter')
              else next.set('chapter', event.target.value)
              setParams(next, { replace: true })
            }}
          >
            <option value="all">All enabled chapters</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {chapter.number}. {chapter.title}
              </option>
            ))}
          </select>
        </div>
        <p className={styles.count}>{visible.length} terms</p>
      </section>

      <ul className={styles.list}>
        {visible.map((term) => {
          const open = selected === term.id
          const chapter = chapterMap.get(term.chapterId)
          return (
            <li key={term.id} className={open ? styles.open : styles.item}>
              <button
                type="button"
                className={styles.termBtn}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  if (open) next.delete('term')
                  else next.set('term', term.id)
                  setParams(next)
                }}
              >
                <strong>{term.term}</strong>
                <span>{chapter ? `Ch. ${chapter.number}` : term.chapterId}</span>
              </button>
              {open ? (
                <div className={styles.details}>
                  <p>{term.definition}</p>
                  {term.example ? <p className={styles.example}>{term.example}</p> : null}
                  {term.related?.length ? (
                    <p className={styles.related}>
                      Related:{' '}
                      {term.related.map((id, index) => {
                        const related = termMap.get(id)
                        const unlocked = related && state.enabledChapterIds.includes(related.chapterId)
                        return (
                          <span key={id}>
                            {index > 0 ? ', ' : null}
                            {unlocked ? (
                              <Link to={`/glossary?term=${id}${chapterId === 'all' ? '' : `&chapter=${chapterId}`}`}>
                                {related.term}
                              </Link>
                            ) : (
                              related?.term ?? id
                            )}
                          </span>
                        )
                      })}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
