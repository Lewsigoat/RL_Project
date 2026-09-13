import type { Term } from '../data/types.ts'

export function normalizeAnswer(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function levenshtein(a: string, b: string): number {
  if (a === b) return 0
  if (a.length === 0) return b.length
  if (b.length === 0) return a.length

  const prev = new Array<number>(b.length + 1)
  const next = new Array<number>(b.length + 1)
  for (let j = 0; j <= b.length; j += 1) prev[j] = j

  for (let i = 1; i <= a.length; i += 1) {
    next[0] = i
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      next[j] = Math.min(next[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
    }
    for (let j = 0; j <= b.length; j += 1) prev[j] = next[j]
  }
  return prev[b.length]
}

export function allowedAnswers(term: Term): string[] {
  const answers = [term.term, ...(term.aliases ?? [])]
  const extra: string[] = []
  for (const answer of answers) {
    const withoutParens = answer.replace(/\s*\([^)]*\)\s*/g, ' ').trim()
    if (withoutParens && withoutParens !== answer) extra.push(withoutParens)
  }
  return [...answers, ...extra]
}

export function answersMatch(term: Term, given: string): boolean {
  const guess = normalizeAnswer(given)
  if (!guess) return false

  for (const candidate of allowedAnswers(term)) {
    const expected = normalizeAnswer(candidate)
    if (!expected) continue
    if (expected === guess) return true
    const maxDistance = expected.length <= 8 ? 1 : 2
    if (Math.abs(expected.length - guess.length) <= maxDistance && levenshtein(expected, guess) <= maxDistance) {
      return true
    }
  }
  return false
}
