import { isCatalog } from '../data/catalog.ts'
import type { Catalog } from '../data/types.ts'
import { newCard, reviewCard, recordQuiz, type CardStats, type Rating } from './srs.ts'
import type { QuizMode } from './quiz.ts'

export const STATE_KEY = 'econ-trainer.v1'
export const CUSTOM_CATALOG_KEY = 'econ-trainer.custom-catalog.v1'

export type QuizHistoryEntry = {
  date: string
  mode: QuizMode
  correct: number
  total: number
}

export type PersistedState = {
  version: 1
  enabledChapterIds: string[]
  cards: Record<string, CardStats>
  streak: number
  lastStudyDate: string | null
  dailyGoal: number
  newCap: number
  reviewsToday: number
  newToday: number
  countersDate: string | null
  quizHistory: QuizHistoryEntry[]
}

export const defaultState: PersistedState = {
  version: 1,
  enabledChapterIds: [],
  cards: {},
  streak: 0,
  lastStudyDate: null,
  dailyGoal: 20,
  newCap: 10,
  reviewsToday: 0,
  newToday: 0,
  countersDate: null,
  quizHistory: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isRating(value: unknown): value is Rating {
  return value === 'again' || value === 'hard' || value === 'good' || value === 'easy'
}

function parseCard(value: unknown): CardStats | null {
  if (!isRecord(value)) return null
  if (typeof value.ease !== 'number' || typeof value.interval !== 'number') return null
  if (typeof value.repetitions !== 'number' || typeof value.due !== 'string') return null
  const card: CardStats = {
    ease: value.ease,
    interval: value.interval,
    repetitions: value.repetitions,
    due: value.due,
    lapses: typeof value.lapses === 'number' ? value.lapses : 0,
    seen: typeof value.seen === 'number' ? value.seen : 0,
    quizSeen: typeof value.quizSeen === 'number' ? value.quizSeen : 0,
    quizCorrect: typeof value.quizCorrect === 'number' ? value.quizCorrect : 0,
  }
  if (isRating(value.lastRating)) card.lastRating = value.lastRating
  if (typeof value.lastReviewed === 'string') card.lastReviewed = value.lastReviewed
  return card
}

export function parseState(value: unknown): PersistedState | null {
  if (!isRecord(value) || value.version !== 1) return null
  if (!Array.isArray(value.enabledChapterIds)) return null
  if (!isRecord(value.cards)) return null

  const cards: Record<string, CardStats> = {}
  for (const [id, raw] of Object.entries(value.cards)) {
    const card = parseCard(raw)
    if (card) cards[id] = card
  }

  return {
    version: 1,
    enabledChapterIds: value.enabledChapterIds.filter((id): id is string => typeof id === 'string'),
    cards,
    streak: typeof value.streak === 'number' ? value.streak : 0,
    lastStudyDate: typeof value.lastStudyDate === 'string' ? value.lastStudyDate : null,
    dailyGoal: typeof value.dailyGoal === 'number' ? value.dailyGoal : 20,
    newCap: typeof value.newCap === 'number' ? value.newCap : 10,
    reviewsToday: typeof value.reviewsToday === 'number' ? value.reviewsToday : 0,
    newToday: typeof value.newToday === 'number' ? value.newToday : 0,
    countersDate: typeof value.countersDate === 'string' ? value.countersDate : null,
    quizHistory: Array.isArray(value.quizHistory)
      ? value.quizHistory.filter((entry): entry is QuizHistoryEntry => {
          return (
            isRecord(entry) &&
            typeof entry.date === 'string' &&
            typeof entry.correct === 'number' &&
            typeof entry.total === 'number' &&
            (entry.mode === 'multiple-choice' || entry.mode === 'type-term' || entry.mode === 'explain')
          )
        })
      : [],
  }
}

export function getCard(state: PersistedState, termId: string, today: string): CardStats {
  return state.cards[termId] ?? newCard(today)
}

export function rollDailyCounters(state: PersistedState, today: string): PersistedState {
  if (state.countersDate === today) return state
  return {
    ...state,
    reviewsToday: 0,
    newToday: 0,
    countersDate: today,
  }
}

export function applyStreak(state: PersistedState, today: string): PersistedState {
  if (state.lastStudyDate === today) return state
  const yesterday = previousDay(today)
  const streak = state.lastStudyDate === yesterday ? state.streak + 1 : 1
  return { ...state, streak, lastStudyDate: today }
}

function previousDay(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() - 1)
  return date.toISOString().slice(0, 10)
}

export function enableChapter(state: PersistedState, chapterId: string): PersistedState {
  if (state.enabledChapterIds.includes(chapterId)) return state
  return { ...state, enabledChapterIds: [...state.enabledChapterIds, chapterId] }
}

export function disableChapter(state: PersistedState, chapterId: string): PersistedState {
  return {
    ...state,
    enabledChapterIds: state.enabledChapterIds.filter((id) => id !== chapterId),
  }
}

export function applyReview(state: PersistedState, termId: string, rating: Rating, today: string): PersistedState {
  const rolled = rollDailyCounters(state, today)
  const current = getCard(rolled, termId, today)
  const wasNew = current.seen === 0
  const nextCard = reviewCard(current, rating, today)
  const next: PersistedState = {
    ...applyStreak(rolled, today),
    cards: { ...rolled.cards, [termId]: nextCard },
    reviewsToday: rolled.reviewsToday + 1,
    newToday: rolled.newToday + (wasNew ? 1 : 0),
  }
  return next
}

export function applyQuizAnswer(state: PersistedState, termId: string, correct: boolean, today: string): PersistedState {
  const rolled = rollDailyCounters(state, today)
  const current = getCard(rolled, termId, today)
  return {
    ...applyStreak(rolled, today),
    cards: { ...rolled.cards, [termId]: recordQuiz(current, correct) },
  }
}

export function appendQuizHistory(state: PersistedState, entry: QuizHistoryEntry): PersistedState {
  return {
    ...state,
    quizHistory: [...state.quizHistory, entry].slice(-40),
  }
}

export function readStorage(storage: Storage | null = defaultStorage()): PersistedState {
  if (!storage) return { ...defaultState, cards: {} }
  try {
    const raw = storage.getItem(STATE_KEY)
    if (!raw) return { ...defaultState, cards: {} }
    return parseState(JSON.parse(raw)) ?? { ...defaultState, cards: {} }
  } catch {
    return { ...defaultState, cards: {} }
  }
}

export function writeStorage(state: PersistedState, storage: Storage | null = defaultStorage()): void {
  if (!storage) return
  storage.setItem(STATE_KEY, JSON.stringify(state))
}

export function readCustomCatalog(storage: Storage | null = defaultStorage()): Catalog | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(CUSTOM_CATALOG_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isCatalog(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function writeCustomCatalog(catalog: Catalog, storage: Storage | null = defaultStorage()): void {
  if (!storage) return
  storage.setItem(CUSTOM_CATALOG_KEY, JSON.stringify(catalog))
}

export function clearCustomCatalog(storage: Storage | null = defaultStorage()): void {
  storage?.removeItem(CUSTOM_CATALOG_KEY)
}

export function exportPayload(state: PersistedState, customCatalog: Catalog | null): string {
  return JSON.stringify(
    {
      kind: 'econ-trainer-export',
      exportedAt: new Date().toISOString(),
      state,
      customCatalog,
    },
    null,
    2,
  )
}

export function parseExport(value: unknown): { state: PersistedState; customCatalog: Catalog | null } | null {
  if (!isRecord(value)) {
    const state = parseState(value)
    return state ? { state, customCatalog: null } : null
  }
  if (value.kind === 'econ-trainer-export') {
    const state = parseState(value.state)
    if (!state) return null
    const customCatalog = isCatalog(value.customCatalog) ? value.customCatalog : null
    return { state, customCatalog }
  }
  const state = parseState(value)
  return state ? { state, customCatalog: isCatalog(value.customCatalog) ? value.customCatalog : null } : null
}

function defaultStorage(): Storage | null {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}
