import rawChapters from './chapters.json'
import rawTerms from './definitions.json'
import type { Catalog, Chapter, Term } from './types.ts'

export const builtInChapters = rawChapters as Chapter[]
export const builtInTerms = rawTerms as Term[]

export function emptyCatalog(): Catalog {
  return { chapters: [], terms: [] }
}

export function mergeCatalog(base: Catalog, extra: Catalog | null | undefined): Catalog {
  if (!extra) return { chapters: [...base.chapters], terms: [...base.terms] }

  const chapters = new Map<string, Chapter>()
  for (const chapter of base.chapters) chapters.set(chapter.id, chapter)
  for (const chapter of extra.chapters ?? []) chapters.set(chapter.id, chapter)

  const terms = new Map<string, Term>()
  for (const term of base.terms) terms.set(term.id, term)
  for (const term of extra.terms ?? []) terms.set(term.id, term)

  return {
    chapters: [...chapters.values()].sort((a, b) => a.number - b.number || a.title.localeCompare(b.title)),
    terms: [...terms.values()],
  }
}

export function termsById(terms: Term[]): Map<string, Term> {
  return new Map(terms.map((term) => [term.id, term]))
}

export function chaptersById(chapters: Chapter[]): Map<string, Chapter> {
  return new Map(chapters.map((chapter) => [chapter.id, chapter]))
}

export function termsForChapter(terms: Term[], chapterId: string): Term[] {
  return terms.filter((term) => term.chapterId === chapterId)
}

export function isCatalog(value: unknown): value is Catalog {
  if (!value || typeof value !== 'object') return false
  const record = value as Partial<Catalog>
  return Array.isArray(record.chapters) && Array.isArray(record.terms)
}

export const builtInCatalog: Catalog = {
  chapters: builtInChapters,
  terms: builtInTerms,
}
