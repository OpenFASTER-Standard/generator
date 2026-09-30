# Task ID: 17

**Title:** First real workspace viewer/editor application

**Status:** pending

**Dependencies:** 6 ✓, 13 ✓, 15, 16

**Priority:** medium

**Description:** The actual integration: log in via workspace-auth (task 6), fetch a real workspace's annotation Turtle, render it with the real resolved values (task 13), edit via re-citation (task 15), and commit via the write client (task 16) -- the first moment anyone can open a page and actually use this platform, not just read about its pieces.

**Details:**

## Why this exists as its own task

Every piece built so far is a library or a single-purpose page: `generator`
(Python library), `@openfaster-standard/ui` (component library),
`workspace-auth` (login only). Nothing wires them together into something
a person opens and uses. This is that integration -- the literal "someone
edited a Wikipedia page" moment for this platform, and the honest measure
of whether "is it live and presentable" can ever be answered yes for the
real thing, not a login-only proof of concept.

## Scope

Depends on every piece below being real and complete: task 6 (login/
token), task 13 (real value display), task 15 (re-citation UI), task 16
(write client). Where this actually lives (a new page inside
`workspace-auth`, or its own new small app) is this task's own brainstorm
decision, grounded in whatever the real shape of tasks 13/15/16 turns out
to be by the time this task starts -- not decided here in advance of that
real information existing.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
