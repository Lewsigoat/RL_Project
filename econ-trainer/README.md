# Econ Trainer

A local study app for economics definitions. You enable chapters one by one; locked chapters stay out of flashcards, quizzes, and the glossary.

## Run it

```bash
cd econ-trainer
npm install
npm run dev
```

Then open the printed local URL (usually `http://localhost:5173`).

```bash
npm test      # unit tests
npm run build # production build
```

Progress is stored in this browser (`localStorage`). Export a backup from the Progress page if you switch machines.

## How to study

1. On **Chapters**, turn on Chapter 1 only.
2. Open **Study**. Space flips a card; `1`–`4` rate Again / Hard / Good / Easy.
3. Spaced repetition (SM-2) schedules the next review. New cards are capped each day.
4. Use **Quiz** for multiple choice, type-the-term, or self-graded explain-it.
5. Enable the next chapter when you want those terms in the queue.

## Add your own definitions

The built-in bank is a 15-chapter intro micro + macro glossary. To use your course wording instead (or as well):

1. Copy `public/custom-terms.example.json`.
2. Add chapters and terms. Custom ids replace built-in terms with the same id.
3. Import the file from **Progress → Import term pack**.

A term looks like:

```json
{
  "id": "opportunity-cost",
  "chapterId": "ch1",
  "term": "Opportunity cost",
  "definition": "The value of the next-best alternative.",
  "example": "Optional.",
  "related": ["scarcity"],
  "aliases": ["alt name"]
}
```

You can also regenerate the built-in JSON after editing `scripts/build_definitions.py`:

```bash
python3 scripts/build_definitions.py
```
