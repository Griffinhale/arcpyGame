# Permit Office Hard-Modern Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Permit Office dashboard into a hard-modern, triage-first civic operations dashboard with selected-application decision briefs, background filing, next-case selection, and queue-cleared auto-close.

**Architecture:** Keep the existing Tkinter Canvas and controller/model split. Add small view-model fields for decision lanes and queue-empty state; keep report tabs additive; change controller behavior so normal decisions do not switch away from Applications; redraw the Canvas with a modern palette, compact queue tabs, card-owned actions, and a slim City Health rail.

**Tech Stack:** Python dataclasses, Tkinter Canvas drawing, ArcPy controller adapters, pytest.

---

## Scope Check

This plan covers dashboard IA, visual modernization, decision flow, queue-clear
behavior, and tests. It does not change gameplay rules or ArcGIS symbology.

## File Structure

- Modify `toolbox/permit_office_arcgis/desk_model.py`
  - Add `ActionLane` and queue/auto-close view-model fields.
  - Build approve/conditions/deny consequence text from the selected case.
- Modify `toolbox/permit_office_arcgis/dashboard.py`
  - Keep normal decisions on Applications.
  - Append report tabs in the background.
  - Auto-select next open case and update map context.
  - Schedule/cancel/pause queue-clear auto-close.
- Modify `toolbox/permit_office_arcgis/desk_view.py`
  - Replace parchment palette with modern civic operations tokens.
  - Remove global action bar.
  - Draw compact queue tabs, decision lanes, card-owned controls, slim pulse rail,
    and queue-cleared state.
- Modify `tests/test_permit_office_desk_view.py`
  - Add model and headless Canvas coverage for action lanes, no global action
    targets, compact queue tabs, slim rail, and queue-cleared controls.
- Modify `tests/test_permit_office_dashboard_controller.py`
  - Add controller coverage for background filing, next selection, auto-close,
    cancel, pause, and final audit routing.

## Tasks

### Task 1: Model Decision Lanes And Queue State

**Files:**
- Modify: `toolbox/permit_office_arcgis/desk_model.py`
- Test: `tests/test_permit_office_desk_view.py`

- [ ] Add failing tests:
  - `test_build_desk_model_adds_decision_lanes_for_selected_case`
  - `test_build_desk_model_marks_queue_cleared_when_no_active_items`
- [ ] Run those tests and verify they fail because `action_lanes`,
  `queue_cleared`, and auto-close fields do not exist.
- [ ] Add `ActionLane` dataclass and fields to `DeskViewModel`.
- [ ] Build three lanes from selected item/template: approve, conditions, deny.
- [ ] Set `queue_cleared` when there are no active docket rows.
- [ ] Rerun focused tests and make them pass.

### Task 2: Controller Triage Loop

**Files:**
- Modify: `toolbox/permit_office_arcgis/dashboard.py`
- Test: `tests/test_permit_office_dashboard_controller.py`

- [ ] Add failing tests:
  - normal decision files report tab but stays on Applications,
  - next open app auto-selects and calls map context,
  - empty queue schedules auto-close,
  - cancel auto-close cancels scheduled callback,
  - switching to Filed Reports pauses auto-close,
  - final week auto-close files final audit report.
- [ ] Run focused controller tests and verify the new tests fail.
- [ ] Add controller state for queue auto-close handle and cancellation.
- [ ] Change `_record_receipt()` so normal decisions do not switch tabs.
- [ ] Add `_select_next_open_item()` and reuse `select_case_context`.
- [ ] Add `_schedule_queue_autoclose()`, `cancel_queue_autoclose()`,
  `_pause_queue_autoclose()`, and `_queue_autoclose_tick()`.
- [ ] Wire cancellation/pause into callbacks and view-model rendering.
- [ ] Rerun focused controller tests.

### Task 3: Modern View Layout

**Files:**
- Modify: `toolbox/permit_office_arcgis/desk_view.py`
- Test: `tests/test_permit_office_desk_view.py`

- [ ] Add failing headless Canvas tests:
  - no global action bar targets are registered,
  - compact queue tabs omit full IDs from visible text,
  - decision lane labels render in the selected app,
  - City Health rail renders only pulse signals,
  - queue-cleared state renders End Week and Cancel Auto Close.
- [ ] Run focused view tests and verify they fail.
- [ ] Replace palette constants with a modern restrained civic palette.
- [ ] Remove global `_draw_action_bar()` call and body budget.
- [ ] Draw selected application as a decision brief.
- [ ] Draw all case controls inside the selected application card.
- [ ] Draw slim City Health pulse rail.
- [ ] Draw queue-cleared state when `model.queue_cleared` is true.
- [ ] Rerun focused view tests.

### Task 4: Full Verification

**Files:**
- Test: full relevant suite

- [ ] Run:
  `python -m pytest tests\test_permit_office_arcgis_geometry.py tests\test_permit_office_dashboard_controller.py tests\test_permit_office_desk_view.py tests\test_permit_office_rules.py tests\test_permit_office_symbology.py -q`
- [ ] Fix regressions without broad refactors.
- [ ] Report remaining manual ArcGIS visual checks.

## Self-Review

Spec coverage: all agreed design decisions are represented by model,
controller, view, and verification tasks.

Placeholder scan: no task relies on undefined future work.

Type consistency: new model names are `ActionLane`, `action_lanes`,
`queue_cleared`, `auto_close_active`, and `auto_close_seconds`.
