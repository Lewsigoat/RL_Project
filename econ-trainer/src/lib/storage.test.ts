import { describe, expect, it } from 'vitest'
import { defaultState, enableChapter, parseExport, parseState, applyReview, rollDailyCounters } from './storage.ts'

describe('storage and progress mutations', () => {
  it('starts with no chapters enabled', () => {
    expect(defaultState.enabledChapterIds).toEqual([])
  })

  it('enables a chapter once', () => {
    const once = enableChapter(defaultState, 'ch1')
    const twice = enableChapter(once, 'ch1')
    expect(once.enabledChapterIds).toEqual(['ch1'])
    expect(twice.enabledChapterIds).toEqual(['ch1'])
  })

  it('rolls daily counters on a new day', () => {
    const reviewed = { ...defaultState, reviewsToday: 8, newToday: 3, countersDate: '2026-09-12' }
    const rolled = rollDailyCounters(reviewed, '2026-09-13')
    expect(rolled.reviewsToday).toBe(0)
    expect(rolled.newToday).toBe(0)
    expect(rolled.countersDate).toBe('2026-09-13')
  })

  it('counts new cards and starts a streak on review', () => {
    const next = applyReview(defaultState, 'scarcity', 'good', '2026-09-13')
    expect(next.reviewsToday).toBe(1)
    expect(next.newToday).toBe(1)
    expect(next.streak).toBe(1)
    expect(next.cards.scarcity.seen).toBe(1)
  })

  it('round-trips a valid export payload', () => {
    const state = enableChapter(defaultState, 'ch1')
    const parsed = parseExport({
      kind: 'econ-trainer-export',
      state,
      customCatalog: { chapters: [], terms: [] },
    })
    expect(parsed?.state.enabledChapterIds).toEqual(['ch1'])
    expect(parsed?.customCatalog).toEqual({ chapters: [], terms: [] })
  })

  it('rejects malformed saved state', () => {
    expect(parseState({ version: 2 })).toBeNull()
    expect(parseState({ version: 1, enabledChapterIds: 'ch1' })).toBeNull()
  })
})
