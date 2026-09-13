import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { builtInCatalog, mergeCatalog } from '../data/catalog.ts'
import type { Catalog } from '../data/types.ts'
import { todayISO } from '../lib/dates.ts'
import type { QuizHistoryEntry } from '../lib/storage.ts'
import {
  appendQuizHistory,
  applyQuizAnswer,
  applyReview,
  clearCustomCatalog,
  defaultState,
  disableChapter,
  enableChapter,
  parseExport,
  readCustomCatalog,
  readStorage,
  rollDailyCounters,
  writeCustomCatalog,
  writeStorage,
  type PersistedState,
} from '../lib/storage.ts'
import type { Rating } from '../lib/srs.ts'

type AppContextValue = {
  state: PersistedState
  catalog: Catalog
  today: string
  enable: (chapterId: string) => void
  disable: (chapterId: string) => void
  review: (termId: string, rating: Rating) => void
  quizAnswer: (termId: string, correct: boolean) => void
  finishQuiz: (entry: QuizHistoryEntry) => void
  setDailyGoal: (dailyGoal: number) => void
  setNewCap: (newCap: number) => void
  importBackup: (value: unknown) => boolean
  resetProgress: () => void
  replaceCustomCatalog: (catalog: Catalog | null) => void
}

const AppStateContext = createContext<AppContextValue | null>(null)

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PersistedState>(() => rollDailyCounters(readStorage(), todayISO()))
  const [customCatalog, setCustomCatalog] = useState<Catalog | null>(() => readCustomCatalog())
  const today = todayISO()
  const viewState = useMemo(
    () => (state.countersDate === today ? state : rollDailyCounters(state, today)),
    [state, today],
  )

  useEffect(() => {
    writeStorage(viewState)
  }, [viewState])

  useEffect(() => {
    if (customCatalog) writeCustomCatalog(customCatalog)
    else clearCustomCatalog()
  }, [customCatalog])

  const catalog = useMemo(() => mergeCatalog(builtInCatalog, customCatalog), [customCatalog])

  const value = useMemo<AppContextValue>(
    () => ({
      state: viewState,
      catalog,
      today,
      enable: (chapterId) => setState((current) => enableChapter(current, chapterId)),
      disable: (chapterId) => setState((current) => disableChapter(current, chapterId)),
      review: (termId, rating) => setState((current) => applyReview(current, termId, rating, today)),
      quizAnswer: (termId, correct) => setState((current) => applyQuizAnswer(current, termId, correct, today)),
      finishQuiz: (entry) => setState((current) => appendQuizHistory(current, entry)),
      setDailyGoal: (dailyGoal) =>
        setState((current) => ({ ...current, dailyGoal: Math.max(1, Math.round(dailyGoal)) })),
      setNewCap: (newCap) => setState((current) => ({ ...current, newCap: Math.max(0, Math.round(newCap)) })),
      importBackup: (value) => {
        const parsed = parseExport(value)
        if (!parsed) return false
        setState(rollDailyCounters(parsed.state, today))
        if (parsed.customCatalog) setCustomCatalog(parsed.customCatalog)
        return true
      },
      resetProgress: () =>
        setState((current) => ({
          ...defaultState,
          enabledChapterIds: current.enabledChapterIds,
          dailyGoal: current.dailyGoal,
          newCap: current.newCap,
          cards: {},
        })),
      replaceCustomCatalog: (next) => setCustomCatalog(next),
    }),
    [catalog, viewState, today],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

export function useAppState(): AppContextValue {
  const value = useContext(AppStateContext)
  if (!value) throw new Error('useAppState must be used inside AppStateProvider')
  return value
}
