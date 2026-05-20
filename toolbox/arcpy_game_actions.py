"""Survey Sweeper action controller.

These functions orchestrate the rules engine and a Store-shaped persistence
seam without importing ArcPy. The eventual ArcGIS Pro integration ships an
ArcPyStore that satisfies the same shape as the test FakeStore.

Schema boundary (Gate B contract):
- ``new_game_action`` and ``reset_action`` may MUTATE schema via
  ``ensure_schema`` / ``clear_all``.
- All other ordinary turn actions call ``assert_schema`` only and never
  mutate schema mid-turn.
"""

from __future__ import annotations

from toolbox import arcpy_game_rules as rules


def new_game_action(store, preset_name: str, seed: int) -> rules.ActionResult:
    """Reset persistence and write a fresh deterministic game."""
    return _start_game_action(store, preset_name=preset_name, seed=seed, action="New Game")


def reset_action(store, preset_name: str, seed: int) -> rules.ActionResult:
    """Clear persisted rows and write a fresh deterministic game."""
    return _start_game_action(store, preset_name=preset_name, seed=seed, action="Reset")


def _start_game_action(
    store,
    *,
    preset_name: str,
    seed: int,
    action: str,
) -> rules.ActionResult:
    store.ensure_schema()
    store.clear_all()

    game = rules.new_game(preset_name, seed=seed)
    store.write_full_game(game)

    message = (
        f"{action}: created {preset_name} board "
        f"({game.state.board_rows}x{game.state.board_cols}) "
        f"with {game.state.hazard_count} hazards, seed={seed}. "
        f"Wrote {len(game.cells)} cells, "
        f"{sum(len(links) for links in game.adjacency.values())} adjacency links."
    )
    gp_operations = ["Schema ensure", "Truncate rows", "Insert rows", "Display state"]
    log_payload: dict[str, object] = {
        "action": action,
        "target_cell_ids": "",
        "result": message,
        "gp_operation": ";".join(gp_operations),
        "status": game.state.status,
        "action_count": game.state.action_count,
    }
    store.append_log(log_payload)

    return rules.ActionResult(
        ok=True,
        action=action,
        changed_cell_ids=[],
        message=message,
        gp_operations=gp_operations,
        log_payload=log_payload,
        refresh_required=True,
    )


def reveal_action(store) -> rules.ActionResult:
    """Reveal the cell currently selected in the store; writes changed rows only."""
    return _selection_action(store, rules.reveal_cells)


def flag_action(store) -> rules.ActionResult:
    """Toggle flags on the currently selected cells; writes changed rows only."""
    return _selection_action(store, rules.flag_cells)


def show_score_action(store) -> rules.ActionResult:
    """Read-only status report; never reads selection or mutates board state."""
    action = "Show Score"
    store.assert_schema()
    game = store.read_game()
    state = game.state
    safe_total = sum(1 for cell in game.cells.values() if not cell.is_hazard)
    last = state.last_message or "(none)"
    message = (
        f"{action}: status={state.status}, seed={state.seed}, "
        f"actions={state.action_count}, "
        f"safe revealed={state.safe_revealed_count}/{safe_total}, "
        f"flags={state.flags_count}/{state.hazard_count}. "
        f"Field update read-only via Selection cursor over GameState. "
        f"Last: {last}"
    )
    gp_operations = ["Selection cursor", "Field update"]
    log_payload: dict[str, object] = {
        "action": action,
        "target_cell_ids": "",
        "result": message,
        "gp_operation": ";".join(gp_operations),
        "status": state.status,
        "action_count": state.action_count,
    }
    store.append_log(log_payload)
    return rules.ActionResult(
        ok=True,
        action=action,
        changed_cell_ids=[],
        message=message,
        gp_operations=gp_operations,
        log_payload=log_payload,
        refresh_required=False,
    )


def _selection_action(store, rule_fn) -> rules.ActionResult:
    store.assert_schema()
    selected = store.read_selection()
    game = store.read_game()
    result = rule_fn(game, selected)

    if result.ok:
        store.write_cells(result.changed_cell_ids, game)
        store.write_state(game.state)
        store.append_log(result.log_payload)
    else:
        store.append_log(_rejection_log(result, selected, game.state))
    return result


def _rejection_log(
    result: rules.ActionResult,
    selected: list[str],
    state: rules.GameState,
) -> dict[str, object]:
    return {
        "action": result.action,
        "target_cell_ids": ",".join(selected),
        "result": result.message,
        "gp_operation": "",
        "status": state.status,
        "action_count": state.action_count,
        "ok": False,
    }
