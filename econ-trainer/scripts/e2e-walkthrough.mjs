import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'

const ARTIFACTS = '/opt/cursor/artifacts'
const BASE = 'http://127.0.0.1:5173'

async function main() {
  await mkdir(ARTIFACTS, { recursive: true })
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    recordVideo: { dir: ARTIFACTS, size: { width: 1400, height: 900 } },
  })
  const page = await context.newPage()
  const failures = []

  const hold = (ms = 800) => page.waitForTimeout(ms)
  const shot = async (name) => {
    await hold(400)
    await page.screenshot({ path: `${ARTIFACTS}/${name}.png`, fullPage: false })
  }

  try {
    await page.goto(BASE, { waitUntil: 'networkidle' })
    await page.evaluate(() => localStorage.clear())
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: /Enable a chapter/i }).waitFor()

    const dueNow = await page.locator('text=due now').locator('xpath=..').locator('strong').innerText()
    if (dueNow.trim() !== '0') failures.push(`expected 0 due on a clean profile, got ${dueNow}`)

    const firstToggle = page.locator('ol input[type="checkbox"]').first()
    if (await firstToggle.isChecked()) failures.push('chapter 1 started enabled')
    await shot('home_chapters_locked')

    await page.waitForTimeout(700)
    await firstToggle.check()
    await page.waitForTimeout(900)
    const dueAfter = await page.locator('text=due now').locator('xpath=..').locator('strong').innerText()
    if (Number(dueAfter) <= 0) failures.push(`enabling chapter 1 should add due cards, got ${dueAfter}`)
    await shot('home_chapter1_enabled')

    await hold()
    await page.getByRole('link', { name: 'Glossary' }).click()
    await page.getByText(/terms$/).waitFor()
    await hold()
    const glossaryCount = await page.locator('p', { hasText: /terms$/ }).innerText()
    const chapter1Count = Number(glossaryCount.split(' ')[0])
    if (chapter1Count < 5) failures.push(`chapter 1 glossary count unexpected: ${glossaryCount}`)
    await page.getByRole('button', { name: /Scarcity/ }).first().click()
    await page.getByText(/limited resources/i).waitFor()
    await shot('glossary_chapter1')

    await hold()
    await page.getByRole('link', { name: 'Quiz' }).click()
    await page.getByRole('heading', { name: /Test only the chapters/i }).waitFor()
    const quizPool = await page.getByText(/unlocked terms are available/).innerText()
    if (!new RegExp(`${chapter1Count} unlocked`).test(quizPool)) failures.push(`quiz pool unexpected: ${quizPool}`)
    await hold()
    await page.getByRole('button', { name: 'Start quiz' }).click()
    await page.getByText(/Question 1/).waitFor()
    await hold()
    const options = page.locator('section >> css=button').filter({ hasNotText: /Check|Next|Start/ })
    await options.first().click()
    await hold(500)
    await page.getByRole('button', { name: 'Check' }).click()
    await page.getByRole('button', { name: 'Next' }).waitFor()
    await shot('quiz_first_question')
    await hold()
    await page.getByRole('button', { name: 'Next' }).click()

    await hold()
    await page.getByRole('link', { name: 'Study' }).click()
    await page.getByRole('heading', { name: /Flashcards/i }).waitFor()
    await hold()
    await page.getByRole('button', { name: /Start \d+ cards/ }).click()
    await page.getByText(/Click or press space to flip/).waitFor()
    await hold()
    await page.getByText(/Click or press space to flip/).click()
    await hold()
    await page.getByRole('button', { name: /Good/ }).click()
    await shot('study_after_first_rating')

    await hold()
    await page.getByRole('link', { name: 'Chapters' }).click()
    await hold()
    await page.locator('ol input[type="checkbox"]').nth(1).check()
    await page.waitForTimeout(700)
    await page.getByRole('link', { name: 'Glossary' }).click()
    const glossary2 = await page.locator('p', { hasText: /terms$/ }).innerText()
    const count2 = Number(glossary2.split(' ')[0])
    if (count2 <= chapter1Count) failures.push(`enabling chapter 2 should grow glossary, got ${glossary2}`)
    await shot('glossary_two_chapters')

    await hold()
    await page.reload({ waitUntil: 'networkidle' })
    await hold()
    await page.getByRole('link', { name: 'Chapters' }).click()
    const stillOn = await page.locator('ol input[type="checkbox"]').first().isChecked()
    const stillOn2 = await page.locator('ol input[type="checkbox"]').nth(1).isChecked()
    if (!stillOn || !stillOn2) failures.push('enabled chapters did not persist after reload')
    const reviews = await page.locator('text=goal').innerText()
    if (!/\d+\/\d+ goal/.test(reviews)) failures.push(`goal meter missing: ${reviews}`)
    await shot('home_persisted_after_reload')

    await page.setViewportSize({ width: 390, height: 844 })
    await page.reload({ waitUntil: 'networkidle' })
    await shot('home_mobile')
  } finally {
    const video = page.video()
    await page.close()
    await context.close()
    await browser.close()
    if (video) {
      const path = await video.path()
      console.log(`VIDEO ${path}`)
    }
  }

  if (failures.length) {
    console.error('FAILURES')
    for (const failure of failures) console.error(`- ${failure}`)
    process.exit(1)
  }
  console.log('E2E walkthrough passed')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
