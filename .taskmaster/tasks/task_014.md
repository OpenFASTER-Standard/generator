# Task ID: 14

**Title:** Migrate existing reclaim-processing flows onto generator

**Status:** pending

**Dependencies:** 8, 9

**Priority:** low

**Description:** Once MiKaDiv-VIB (task 8) and KaFE (task 9) are real, migrate the existing production reclaim-processing code (app/docapi, FilledDocumentCreatorService) to run on top of the generator platform instead of its own separate, hand-maintained logic -- the actual business payoff this whole effort was building toward.

**Details:**

## Why this exists as its own task

Stated explicitly at the very start of this effort (2026-09-14), as the
real-world payoff for finishing the ontology work, and never mentioned
again since: "I want to get done with mikadiv-vib and kafe as soon as
possible, because all the other reclaim processes (see app/docapi and
also FilledDocumentCreatorService in app) should be migrated into this as
well. but that's a follow up once we've finished mikadiv-vib and kafe."

This is the one task in the whole roadmap that closes the loop back to
Divizend's own production system -- everything else in this roadmap is
platform-building; this is the task that makes the platform's existence
actually matter to a real, currently-running business process.

## Real current state (to verify freshly at this task's own brainstorm,
not assumed here)

`app/docapi` and `FilledDocumentCreatorService` (in the separate `app`
monorepo) currently implement German reclaim filing logic independently
of anything in `generator`. This task's brainstorm must ground itself in
the real, current state of that code at the time it starts, not this
description -- per this project's own standing rule, nothing here is
exempt from being re-verified against real sources, including this
task's own premise.

## Scope

Deliberately sequenced last among the ontology-completion tasks --
depends on tasks 8 and 9 both being real and complete, since the reclaim
flows this task migrates span both MiKaDiv-VIB and KaFE, not just the
already-built MiKaDiv-FM.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
