import { addDays } from './dates.ts'

export type Rating = 'again' | 'hard' | 'good' | 'easy'

export const RATING_QUALITY: Record<Rating, number> = {
  again: 1,
  hard: 3,
  good: 4,
  easy: 5,
}

export type CardStats = {
  ease: number
  interval: number
  repetitions: number
  due: string
  lapses: number
  lastRating?: Rating
  lastReviewed?: string
  seen: number
  quizSeen: number
  quizCorrect: number
}

export function newCard(today: string): CardStats {
  return {
    ease: 2.5,
    interval: 0,
    repetitions: 0,
    due: today,
    lapses: 0,
    seen: 0,
    quizSeen: 0,
    quizCorrect: 0,
  }
}

export function reviewCard(card: CardStats, rating: Rating, today: string): CardStats {
  const quality = RATING_QUALITY[rating]
  let ease = card.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
  if (ease < 1.3) ease = 1.3

  let repetitions = card.repetitions
  let interval = card.interval
  let lapses = card.lapses

  if (quality < 3) {
    repetitions = 0
    interval = 1
    lapses += 1
  } else if (repetitions === 0) {
    interval = 1
    repetitions = 1
  } else if (repetitions === 1) {
    interval = rating === 'hard' ? 3 : rating === 'easy' ? 8 : 6
    repetitions = 2
  } else {
    const factor = rating === 'hard' ? 1.2 : rating === 'easy' ? ease * 1.3 : ease
    interval = Math.max(1, Math.round(interval * factor))
    repetitions += 1
  }

  return {
    ...card,
    ease,
    interval,
    repetitions,
    lapses,
    due: addDays(today, interval),
    lastRating: rating,
    lastReviewed: today,
    seen: card.seen + 1,
  }
}

export function recordQuiz(card: CardStats, correct: boolean): CardStats {
  return {
    ...card,
    quizSeen: card.quizSeen + 1,
    quizCorrect: card.quizCorrect + (correct ? 1 : 0),
  }
}

export function termMastery(card: CardStats | undefined): number {
  if (!card || card.seen === 0) return 0
  if (card.repetitions === 0) return 0.12
  const fromInterval = Math.min(1, card.interval / 21)
  const fromEase = Math.min(1, Math.max(0, card.ease - 1.3) / 1.4)
  const fromReps = Math.min(1, card.repetitions / 5)
  return Math.min(1, 0.4 * fromInterval + 0.3 * fromEase + 0.3 * fromReps)
}

export function isWeakCard(card: CardStats | undefined): boolean {
  if (!card || card.seen === 0) return false
  return card.ease < 2.1 || card.lapses >= 2 || card.lastRating === 'again'
}

export function isNewCard(card: CardStats | undefined): boolean {
  return !card || card.seen === 0
}
