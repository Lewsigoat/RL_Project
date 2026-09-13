import type { Term } from '../data/types.ts'
import { answersMatch } from './matching.ts'
import { shuffle } from './shuffle.ts'

export type QuizMode = 'multiple-choice' | 'type-term' | 'explain'

export type MultipleChoiceQuestion = {
  mode: 'multiple-choice'
  term: Term
  prompt: string
  options: string[]
  answer: string
}

export type TypeTermQuestion = {
  mode: 'type-term'
  term: Term
  prompt: string
}

export type ExplainQuestion = {
  mode: 'explain'
  term: Term
  prompt: string
  reveal: string
}

export type QuizQuestion = MultipleChoiceQuestion | TypeTermQuestion | ExplainQuestion

export function pickDistractors(
  correct: Term,
  pool: Term[],
  count: number,
  rng: () => number = Math.random,
): Term[] {
  const sameChapter = pool.filter((term) => term.id !== correct.id && term.chapterId === correct.chapterId)
  const otherChapters = pool.filter((term) => term.id !== correct.id && term.chapterId !== correct.chapterId)
  return [...shuffle(sameChapter, rng), ...shuffle(otherChapters, rng)].slice(0, count)
}

export function buildMultipleChoice(
  term: Term,
  pool: Term[],
  rng: () => number = Math.random,
): MultipleChoiceQuestion | null {
  const distractors = pickDistractors(term, pool, 3, rng)
  if (distractors.length < 1) return null
  const options = shuffle([term.term, ...distractors.map((item) => item.term)], rng)
  return {
    mode: 'multiple-choice',
    term,
    prompt: term.definition,
    options,
    answer: term.term,
  }
}

export function buildTypeTerm(term: Term): TypeTermQuestion {
  return {
    mode: 'type-term',
    term,
    prompt: term.definition,
  }
}

export function buildExplain(term: Term): ExplainQuestion {
  return {
    mode: 'explain',
    term,
    prompt: term.term,
    reveal: term.definition,
  }
}

export function gradeMultipleChoice(question: MultipleChoiceQuestion, choice: string): boolean {
  return choice === question.answer
}

export function gradeTypeTerm(question: TypeTermQuestion, given: string): boolean {
  return answersMatch(question.term, given)
}

export function buildQuiz(
  mode: QuizMode,
  terms: Term[],
  count: number,
  rng: () => number = Math.random,
): QuizQuestion[] {
  const selected = shuffle(terms, rng).slice(0, Math.max(0, count))
  const questions: QuizQuestion[] = []
  for (const term of selected) {
    if (mode === 'multiple-choice') {
      const question = buildMultipleChoice(term, terms, rng)
      if (question) questions.push(question)
    } else if (mode === 'type-term') {
      questions.push(buildTypeTerm(term))
    } else {
      questions.push(buildExplain(term))
    }
  }
  return questions
}
