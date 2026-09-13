import { describe, expect, it } from 'vitest'
import { addDays } from './dates.ts'
import { isNewCard, isWeakCard, newCard, reviewCard, termMastery } from './srs.ts'

describe('reviewCard SM-2', () => {
  it('schedules the first good review for tomorrow', () => {
    const next = reviewCard(newCard('2026-09-13'), 'good', '2026-09-13')
    expect(next.seen).toBe(1)
    expect(next.repetitions).toBe(1)
    expect(next.interval).toBe(1)
    expect(next.due).toBe('2026-09-14')
  })

  it('uses a longer interval after the second successful review', () => {
    const first = reviewCard(newCard('2026-09-13'), 'good', '2026-09-13')
    const second = reviewCard(first, 'good', '2026-09-14')
    expect(second.repetitions).toBe(2)
    expect(second.interval).toBe(6)
    expect(second.due).toBe(addDays('2026-09-14', 6))
  })

  it('resets repetitions when rated again', () => {
    const learned = reviewCard(reviewCard(newCard('2026-09-13'), 'good', '2026-09-13'), 'good', '2026-09-14')
    const failed = reviewCard(learned, 'again', '2026-09-20')
    expect(failed.repetitions).toBe(0)
    expect(failed.interval).toBe(1)
    expect(failed.lapses).toBe(1)
    expect(failed.due).toBe('2026-09-21')
  })

  it('never lets ease drop below 1.3', () => {
    let card = newCard('2026-09-13')
    for (let i = 0; i < 20; i += 1) {
      card = reviewCard(card, 'again', addDays('2026-09-13', i))
    }
    expect(card.ease).toBeGreaterThanOrEqual(1.3)
  })

  it('treats unseen cards as new and recent misses as weak', () => {
    expect(isNewCard(undefined)).toBe(true)
    expect(isNewCard(newCard('2026-09-13'))).toBe(true)
    const missed = reviewCard(newCard('2026-09-13'), 'again', '2026-09-13')
    expect(isWeakCard(missed)).toBe(true)
    expect(termMastery(undefined)).toBe(0)
    expect(termMastery(missed)).toBeGreaterThan(0)
  })
})
