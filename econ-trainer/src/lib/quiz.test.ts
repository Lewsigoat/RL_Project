import { describe, expect, it } from 'vitest'
import type { Term } from '../data/types.ts'
import { buildMultipleChoice, buildQuiz, pickDistractors } from './quiz.ts'

const terms: Term[] = [
  { id: 'a', chapterId: 'ch1', term: 'Alpha', definition: 'First' },
  { id: 'b', chapterId: 'ch1', term: 'Beta', definition: 'Second' },
  { id: 'c', chapterId: 'ch1', term: 'Gamma', definition: 'Third' },
  { id: 'd', chapterId: 'ch2', term: 'Delta', definition: 'Fourth' },
]

describe('quiz helpers', () => {
  it('prefers distractors from the same chapter', () => {
    const distractors = pickDistractors(terms[0], terms, 3, () => 0)
    expect(distractors.slice(0, 2).map((term) => term.id).sort()).toEqual(['b', 'c'])
    expect(distractors[2]?.id).toBe('d')
  })

  it('builds a four-option multiple-choice question', () => {
    const question = buildMultipleChoice(terms[0], terms, () => 0)
    expect(question).not.toBeNull()
    expect(question?.options).toHaveLength(4)
    expect(question?.options).toContain('Alpha')
    expect(question?.answer).toBe('Alpha')
  })

  it('returns no questions from an empty enabled pool', () => {
    expect(buildQuiz('multiple-choice', [], 10)).toEqual([])
  })
})
