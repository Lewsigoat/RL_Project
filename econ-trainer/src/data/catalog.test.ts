import { describe, expect, it } from 'vitest'
import { builtInCatalog, isCatalog, mergeCatalog } from './catalog.ts'

describe('catalog', () => {
  it('loads Lucas\'s Edexcel IGCSE EC2 bank', () => {
    expect(builtInCatalog.chapters).toHaveLength(42)
    expect(builtInCatalog.terms.length).toBeGreaterThan(150)
    expect(new Set(builtInCatalog.terms.map((term) => term.id)).size).toBe(builtInCatalog.terms.length)
    expect(builtInCatalog.terms.every((term) => term.definition.length > 0)).toBe(true)
    expect(builtInCatalog.chapters.every((chapter) => builtInCatalog.terms.some((term) => term.chapterId === chapter.id))).toBe(true)
    expect(builtInCatalog.terms.find((term) => term.id === 'scarcity')?.definition).toMatch(/limited resources/i)
    expect(builtInCatalog.terms.find((term) => term.id === 'savings-ratio')?.chapterId).toBe('ch31')
  })

  it('lets a custom pack override a term and add a chapter', () => {
    const merged = mergeCatalog(builtInCatalog, {
      chapters: [{ id: 'ch99', number: 99, title: 'My notes', summary: 'Custom' }],
      terms: [
        {
          id: 'scarcity',
          chapterId: 'ch1',
          term: 'Scarcity (my wording)',
          definition: 'Custom definition.',
        },
        {
          id: 'my-term',
          chapterId: 'ch99',
          term: 'My term',
          definition: 'From my notes.',
        },
      ],
    })
    expect(merged.chapters.some((chapter) => chapter.id === 'ch99')).toBe(true)
    expect(merged.terms.find((term) => term.id === 'scarcity')?.term).toBe('Scarcity (my wording)')
    expect(merged.terms.some((term) => term.id === 'my-term')).toBe(true)
  })

  it('validates catalog shape', () => {
    expect(isCatalog({ chapters: [], terms: [] })).toBe(true)
    expect(isCatalog({ terms: [] })).toBe(false)
  })
})
