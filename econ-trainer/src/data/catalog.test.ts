import { describe, expect, it } from 'vitest'
import { builtInCatalog, isCatalog, mergeCatalog } from './catalog.ts'

describe('catalog', () => {
  it('loads the built-in chapter bank', () => {
    expect(builtInCatalog.chapters).toHaveLength(15)
    expect(builtInCatalog.terms.length).toBeGreaterThan(200)
    expect(new Set(builtInCatalog.terms.map((term) => term.id)).size).toBe(builtInCatalog.terms.length)
  })

  it('lets a custom pack override a term and add a chapter', () => {
    const merged = mergeCatalog(builtInCatalog, {
      chapters: [{ id: 'ch16', number: 16, title: 'My notes', summary: 'Custom' }],
      terms: [
        {
          id: 'scarcity',
          chapterId: 'ch1',
          term: 'Scarcity (my wording)',
          definition: 'Custom definition.',
        },
        {
          id: 'my-term',
          chapterId: 'ch16',
          term: 'My term',
          definition: 'From my notes.',
        },
      ],
    })
    expect(merged.chapters.some((chapter) => chapter.id === 'ch16')).toBe(true)
    expect(merged.terms.find((term) => term.id === 'scarcity')?.term).toBe('Scarcity (my wording)')
    expect(merged.terms.some((term) => term.id === 'my-term')).toBe(true)
  })

  it('validates catalog shape', () => {
    expect(isCatalog({ chapters: [], terms: [] })).toBe(true)
    expect(isCatalog({ terms: [] })).toBe(false)
  })
})
