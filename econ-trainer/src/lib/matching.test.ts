import { describe, expect, it } from 'vitest'
import type { Term } from '../data/types.ts'
import { answersMatch, levenshtein, normalizeAnswer } from './matching.ts'

const gdp: Term = {
  id: 'gdp',
  chapterId: 'ch10',
  term: 'Gross domestic product',
  definition: 'The market value of all final goods and services produced within a country.',
  aliases: ['GDP'],
}

describe('answer matching', () => {
  it('normalizes case, punctuation, and spacing', () => {
    expect(normalizeAnswer('  GDP — (gross)  ')).toBe('gdp gross')
  })

  it('accepts the official term and aliases', () => {
    expect(answersMatch(gdp, 'gross domestic product')).toBe(true)
    expect(answersMatch(gdp, 'GDP')).toBe(true)
  })

  it('accepts a single-character typo on a long answer', () => {
    expect(answersMatch(gdp, 'gross domestic prodcut')).toBe(true)
  })

  it('rejects a different term', () => {
    expect(answersMatch(gdp, 'gross national product')).toBe(false)
    expect(answersMatch(gdp, '')).toBe(false)
  })

  it('computes levenshtein distance', () => {
    expect(levenshtein('kitten', 'sitting')).toBe(3)
    expect(levenshtein('gdp', 'gdp')).toBe(0)
  })
})
