# Task ID: 11

**Title:** Generate the public spec/Bikeshed site as a projection of the annotation model

**Status:** pending

**Dependencies:** 1 ✓, 2 ✓

**Priority:** medium

**Description:** Make openfaster.org's own public specification site a generated output of the real annotation_model data, not a separately-maintained artifact.

**Details:**

## Why this exists as its own task

Stated explicitly, twice, six weeks apart: first on 2026-09-14 ("the
entire bikeshed site SHOULD get touched by this, i.e. all be generated
based on the new one single point of truth as well instead of staying
something separate"), and again by the operator's own unprompted
observation on 2026-09-30, during this same session's full-vision
reconstruction: "right now it's not really there yet, because... the
bike shed documentation is still a separate artifact." Never built,
and self-identified as still missing on both ends of this project's
timeline.

## Real current state

`spec`/Bikeshed content on openfaster.org is currently hand-authored,
independent of `annotation_model`'s own real stored shapes and citations
-- the exact "dead markdown files again" failure mode this project has
otherwise deliberately avoided everywhere else (source, transformation,
and UI are all already required to stay traceable to real annotation
data; the spec site is the one remaining exception).

## Scope

Brainstorm a real transformation (likely reusing task 2's own declarative
transformation layer directly, given Bikeshed output is itself just
another rendered artifact of the same underlying shapes) that generates
the spec site's real content from `annotation_model`'s own stored
citations, replacing the hand-authored version outright rather than
syncing the two.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
