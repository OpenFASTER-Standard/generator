# Task ID: 18

**Title:** Self-asserted corrections as a first-class source kind

**Status:** pending

**Dependencies:** 13

**Priority:** low

**Description:** Introduce the third source kind named in this project's original vision -- a correction not grounded in any existing official document (e.g. fixing a typo, adding a missing English translation) -- treated identically to an XSD or PDF citation, per the project's own standing rule that structure and content, and every source kind, get the same real treatment.

**Details:**

## Why this exists as its own task, sequenced after re-citation editing

Stated explicitly, early in this project's history: "I want full
provenance for every piece of data... we'll have at least three sources
further down the line: the XSDs, the PDFs and then also my own
corrections, e.g. correcting typos in descriptions, adding missing
english versions etc." And later, sharpened further: "all the 'review
results' should just become yet another source, which is then treated
identically (using References) like any other source" -- correction
provenance is not a special case bolted onto the citation model, it's a
third real source kind alongside XSD/XPath and PDF/SVG.

This is real, named, and not yet designed at all -- deliberately
sequenced after task 15 (re-citation editing) proves out the *simpler*
case (re-pointing to a different span of an *existing* document) before
tackling the harder one (a value with no source document to point to at
all).

## Scope

A new selector/source kind in `annotation_model` (task 1's own package) --
what a "correction" cites when there is nothing to cite, and how it
remains provably attributable (who asserted it, when) with the same rigor
`annotate_xpath`/`annotate_svg` already give real document citations.
Real design question, not yet explored -- this task's own brainstorm
starts from a genuinely open question, not a pre-decided mechanism.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
