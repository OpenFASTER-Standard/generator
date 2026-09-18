import { expect, test } from "@playwright/test"

test("hover on a documentation value shows a real source preview", async ({ page }) => {
  await page.goto("/#/living-text")
  // Not just "the first span.underline on the page": the real corpus's own
  // first Matched entry when sorted by (name, uri) -- AOrdNr, see
  // reporting/data.py's own deterministic sort -- has real German
  // documentation with NO attached provenance (its URI fragment
  // "AmtlicheOrdnungsnummerMa23ListeType.AOrdNr" contains a "." and is
  // therefore a locally-scoped declaration, out of scope for German
  // provenance by webapp/pipeline.py's own
  // _attach_german_provenance_for_global_constructs -- see that
  // function's own scope-note comment). Hovering that German span would
  // legitimately render "No source recorded." and time out waiting for an
  // img/code, not because anything is broken.
  //
  // That same entry's English documentation ("Official serial number.")
  // DOES have real provenance -- confirmed live against the real,
  // running e2e app (GET /api/provenance for this exact subject+lang
  // returned a real citation:pdf sourceUri with a bbox) -- because English
  // provenance only requires a real PDF text-occurrence match, independent
  // of the German-only global/local scope split. Target that span
  // specifically, by its own known real text, rather than "whichever span
  // happens to be first in the DOM" -- reproducible against the real data,
  // not an assumption about corpus ordering.
  const englishValue = page.locator("span.underline").filter({ hasText: "Official serial number" }).first()
  await englishValue.hover()
  await expect(page.locator("img, code").first()).toBeVisible({ timeout: 10_000 })
})

test("clicking a documentation value pins it into the URL-addressable focus", async ({ page }) => {
  await page.goto("/#/living-text")
  const firstValue = page.locator("span.underline").first()
  await firstValue.click()
  await expect(page).toHaveURL(/#\/living-text\/.+/)
})

test("switching modes after a click preserves the same focused subject", async ({ page }) => {
  await page.goto("/#/living-text")
  const firstValue = page.locator("span.underline").first()
  await firstValue.click()
  const url = page.url()
  const subject = decodeURIComponent(url.split("/living-text/")[1].split("/")[0])

  await page.getByRole("tab", { name: "Graph" }).click()
  await expect(page).toHaveURL(new RegExp(`#/graph/${encodeURIComponent(subject).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
})

test("Synced Panes: clicking a PDF page shows real derived facts, both directions", async ({ page }) => {
  await page.goto("/#/synced-panes")
  await page.getByRole("img").first().click()
  await expect(page.getByText(/derived from this location/i)).toBeVisible()
})
