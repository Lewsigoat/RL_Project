import type { Chapter, Term } from '../data/types.ts'
import { isDue } from './dates.ts'
import { isNewCard, isWeakCard, termMastery, type CardStats } from './srs.ts'
import { shuffle } from './shuffle.ts'

export type StudyMode = 'mixed' | 'new' | 'review'

export function enabledTerms(terms: Term[], enabledChapterIds: readonly string[]): Term[] {
  const enabled = new Set(enabledChapterIds)
  return terms.filter((term) => enabled.has(term.chapterId))
}

export function enabledChapters(chapters: Chapter[], enabledChapterIds: readonly string[]): Chapter[] {
  const enabled = new Set(enabledChapterIds)
  return chapters.filter((chapter) => enabled.has(chapter.id))
}

export function filterTermsByChapter(terms: Term[], chapterId: string | 'all'): Term[] {
  if (chapterId === 'all') return terms
  return terms.filter((term) => term.chapterId === chapterId)
}

export function searchTerms(terms: Term[], query: string): Term[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return terms
  return terms.filter((term) => {
    const haystack = [term.term, term.definition, term.example ?? '', ...(term.aliases ?? [])]
      .join(' ')
      .toLowerCase()
    return haystack.includes(needle)
  })
}

export function dueReviewTerms(
  terms: Term[],
  cards: Record<string, CardStats>,
  today: string,
): Term[] {
  return terms.filter((term) => {
    const card = cards[term.id]
    return card && card.seen > 0 && isDue(card.due, today)
  })
}

export function newTerms(terms: Term[], cards: Record<string, CardStats>): Term[] {
  return terms.filter((term) => isNewCard(cards[term.id]))
}

export function buildStudyQueue(options: {
  terms: Term[]
  cards: Record<string, CardStats>
  today: string
  newCapRemaining: number
  mode: StudyMode
  shuffleQueue?: boolean
  rng?: () => number
}): Term[] {
  const review = dueReviewTerms(options.terms, options.cards, options.today)
  const fresh = newTerms(options.terms, options.cards).slice(0, Math.max(0, options.newCapRemaining))

  let queue: Term[]
  if (options.mode === 'new') queue = fresh
  else if (options.mode === 'review') queue = review
  else queue = [...review, ...fresh]

  return options.shuffleQueue ? shuffle(queue, options.rng) : queue
}

export function chapterMastery(
  terms: Term[],
  cards: Record<string, CardStats>,
  chapterId: string,
): { score: number; seen: number; total: number } {
  const chapterTerms = terms.filter((term) => term.chapterId === chapterId)
  if (chapterTerms.length === 0) return { score: 0, seen: 0, total: 0 }
  const seen = chapterTerms.filter((term) => (cards[term.id]?.seen ?? 0) > 0).length
  const score = chapterTerms.reduce((sum, term) => sum + termMastery(cards[term.id]), 0) / chapterTerms.length
  return { score, seen, total: chapterTerms.length }
}

export function weakTerms(terms: Term[], cards: Record<string, CardStats>): Term[] {
  return terms
    .filter((term) => isWeakCard(cards[term.id]))
    .sort((a, b) => (cards[a.id]?.ease ?? 2.5) - (cards[b.id]?.ease ?? 2.5))
}

export function dueCounts(
  terms: Term[],
  cards: Record<string, CardStats>,
  today: string,
  newCapRemaining: number,
): { review: number; nextNew: number; total: number } {
  const review = dueReviewTerms(terms, cards, today).length
  const nextNew = Math.min(newCapRemaining, newTerms(terms, cards).length)
  return { review, nextNew, total: review + nextNew }
}
