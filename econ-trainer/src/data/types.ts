export type Chapter = {
  id: string
  number: number
  title: string
  summary: string
}

export type Term = {
  id: string
  chapterId: string
  term: string
  definition: string
  example?: string
  related?: string[]
  aliases?: string[]
}

export type Catalog = {
  chapters: Chapter[]
  terms: Term[]
}
