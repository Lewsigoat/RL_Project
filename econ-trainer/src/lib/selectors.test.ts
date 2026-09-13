import { describe, expect, it } from 'vitest'
import type { Term } from '../data/types.ts'
import { newCard, reviewCard } from './srs.ts'
import { buildStudyQueue, enabledTerms, searchTerms } from './selectors.ts'

const terms: Term[] = [
  { id: 'scarcity', chapterId: 'ch1', term: 'Scarcity', definition: 'Wants exceed resources.' },
  { id: 'gdp', chapterId: 'ch10', term: 'GDP', definition: 'Output inside a country.' },
  { id: 'tariff', chapterId: 'ch15', term: 'Tariff', definition: 'A tax on imports.' },
]

describe('chapter filtering', () => {
  it('excludes disabled chapters from study pools', () => {
    expect(enabledTerms(terms, []).map((term) => term.id)).toEqual([])
    expect(enabledTerms(terms, ['ch1']).map((term) => term.id)).toEqual(['scarcity'])
    expect(enabledTerms(terms, ['ch1', 'ch15']).map((term) => term.id).sort()).toEqual(['scarcity', 'tariff'])
  })

  it('keeps disabled-chapter terms out of the due queue', () => {
    const cards = {
      scarcity: reviewCard(newCard('2026-09-10'), 'good', '2026-09-10'),
      gdp: reviewCard(newCard('2026-09-10'), 'good', '2026-09-10'),
    }
    const enabled = enabledTerms(terms, ['ch1'])
    const queue = buildStudyQueue({
      terms: enabled,
      cards,
      today: '2026-09-13',
      newCapRemaining: 10,
      mode: 'mixed',
    })
    expect(queue.map((term) => term.id)).toEqual(['scarcity'])
  })

  it('respects the new-card cap', () => {
    const queue = buildStudyQueue({
      terms: enabledTerms(terms, ['ch1', 'ch10', 'ch15']),
      cards: {},
      today: '2026-09-13',
      newCapRemaining: 2,
      mode: 'new',
    })
    expect(queue).toHaveLength(2)
  })

  it('searches term names and definitions', () => {
    expect(searchTerms(terms, 'imports').map((term) => term.id)).toEqual(['tariff'])
  })
})
