import copy

import pytest

from toolbox import arcpy_game_rules as rules


def test_cell_ids_are_zero_padded_and_preserve_board_order():
    ids = rules.generate_cell_ids(5, 5)

    assert len(ids) == 25
    assert len(set(ids)) == 25
    assert ids[0] == "R00C00"
    assert ids[-1] == "R04C04"
    assert sorted(ids) == ids
    assert rules.cell_id(3, 4) == "R03C04"


def test_board_presets_are_frozen_for_mvp():
    tiny = rules.get_board_preset("Tiny Demo")
    small = rules.get_board_preset("Small")

    assert tiny.rows == 5
    assert tiny.cols == 5
    assert tiny.hazard_count == 4
    assert small.rows == 7
    assert small.cols == 7
    assert small.hazard_count == 8

    with pytest.raises(ValueError, match="Unknown board preset"):
        rules.get_board_preset("Medium")


def test_adjacency_has_expected_neighbor_counts_and_metadata():
    adjacency = rules.build_adjacency(5, 5)

    assert len(adjacency["R00C00"]) == 3
    assert len(adjacency["R00C02"]) == 5
    assert len(adjacency["R02C02"]) == 8

    center_neighbors = {link.neighbor_id: link for link in adjacency["R02C02"]}
    assert center_neighbors["R01C02"].touch_type == "edge"
    assert center_neighbors["R01C01"].touch_type == "corner"
    assert center_neighbors["R01C02"].weight == 1.0

    for cid, links in adjacency.items():
        neighbor_ids = [link.neighbor_id for link in links]
        assert cid not in neighbor_ids
        assert len(neighbor_ids) == len(set(neighbor_ids))

    assert sum(len(links) for links in adjacency.values()) == 144


def test_hazard_placement_is_deterministic_unique_and_valid():
    ids = rules.generate_cell_ids(5, 5)

    hazards_a = rules.place_hazards(ids, hazard_count=4, seed=2026)
    hazards_b = rules.place_hazards(ids, hazard_count=4, seed=2026)

    assert hazards_a == hazards_b
    assert len(hazards_a) == 4
    assert hazards_a <= set(ids)

    with pytest.raises(ValueError, match="Cannot place"):
        rules.place_hazards(ids, hazard_count=26, seed=2026)


def test_neighbor_counts_for_hand_authored_three_by_three_board():
    ids = rules.generate_cell_ids(3, 3)
    adjacency = rules.build_adjacency(3, 3)
    hazards = {"R00C00", "R02C02"}

    counts = rules.compute_neighbor_counts(ids, hazards, adjacency)

    assert counts["R00C00"] == 0
    assert counts["R00C01"] == 1
    assert counts["R01C01"] == 2
    assert counts["R02C01"] == 1
    assert counts["R02C02"] == 0


def test_new_game_initializes_hidden_playing_state():
    game = rules.new_game("Tiny Demo", seed=2026)

    assert len(game.cells) == 25
    assert sum(len(links) for links in game.adjacency.values()) == 144
    assert game.state.status == "playing"
    assert game.state.seed == 2026
    assert game.state.safe_revealed_count == 0
    assert game.state.flags_count == 0
    assert game.state.action_count == 0
    assert game.state.hazard_count == 4
    assert all(not cell.revealed for cell in game.cells.values())
    assert all(not cell.flagged for cell in game.cells.values())
    assert {cell.display_state for cell in game.cells.values()} == {"hidden"}


def test_reveal_safe_clue_updates_counts_display_and_message():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00"})

    result = rules.reveal_cells(game, ["R00C01"])

    assert result.ok is True
    assert result.changed_cell_ids == ["R00C01"]
    assert game.cells["R00C01"].revealed is True
    assert game.cells["R00C01"].turn_revealed == 1
    assert game.cells["R00C01"].display_state == "revealed_clue"
    assert game.state.safe_revealed_count == 1
    assert game.state.action_count == 1
    assert game.state.status == "playing"
    assert "Reveal / Scout" in result.message
    assert "R00C01" in result.message
    assert "Selection cursor" in result.message
    assert "Adjacency lookup" in result.message
    assert "Field update" in result.gp_operations
    assert result.log_payload["target_cell_ids"] == "R00C01"


def test_reveal_safe_empty_does_not_flood_reveal_in_mvp():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00"})

    result = rules.reveal_cells(game, ["R02C02"])

    assert result.ok is True
    assert game.cells["R02C02"].display_state == "revealed_empty"
    assert game.state.safe_revealed_count == 1
    assert [cid for cid, cell in game.cells.items() if cell.revealed] == ["R02C02"]


def test_reveal_hazard_loses_and_reveals_all_hazards():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00", "R02C02"})

    result = rules.reveal_cells(game, ["R00C00"])

    assert result.ok is True
    assert game.state.status == "lost"
    assert game.cells["R00C00"].revealed is True
    assert game.cells["R00C00"].hazard_hit is True
    assert game.cells["R00C00"].display_state == "hazard_hit"
    assert game.cells["R02C02"].display_state == "hazard_revealed"
    assert "LOST" in result.message


def test_reveal_validation_is_atomic_and_rejects_bad_selection():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00"})

    _assert_no_mutation(game, lambda: rules.reveal_cells(game, []), "Select exactly one")
    _assert_no_mutation(game, lambda: rules.reveal_cells(game, ["R00C01", "R00C02"]), "Select exactly one")
    _assert_no_mutation(game, lambda: rules.reveal_cells(game, ["R99C99"]), "Unknown cell")

    rules.flag_cells(game, ["R00C01"])
    before = copy.deepcopy(game)
    result = rules.reveal_cells(game, ["R00C01"])
    assert result.ok is False
    assert "flagged" in result.message
    assert game == before


def test_mutating_actions_reject_after_terminal_state():
    game = _manual_game(rows=2, cols=2, hazards={"R00C00"})
    rules.reveal_cells(game, ["R00C00"])

    _assert_no_mutation(game, lambda: rules.reveal_cells(game, ["R00C01"]), "status is lost")
    _assert_no_mutation(game, lambda: rules.flag_cells(game, ["R00C01"]), "status is lost")


def test_flag_toggle_supports_multiple_cells_and_updates_counts():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00"})

    result = rules.flag_cells(game, ["R00C01", "R02C02"])

    assert result.ok is True
    assert result.changed_cell_ids == ["R00C01", "R02C02"]
    assert game.cells["R00C01"].flagged is True
    assert game.cells["R02C02"].flagged is True
    assert game.cells["R00C01"].display_state == "flagged"
    assert game.state.flags_count == 2
    assert game.state.action_count == 1
    assert "Flag / Mark" in result.message
    assert "Selection cursor" in result.message

    result = rules.flag_cells(game, ["R00C01"])
    assert result.ok is True
    assert game.cells["R00C01"].flagged is False
    assert game.cells["R02C02"].flagged is True
    assert game.state.flags_count == 1
    assert game.state.action_count == 2


def test_flag_validation_is_atomic():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00"})
    rules.reveal_cells(game, ["R02C02"])

    _assert_no_mutation(game, lambda: rules.flag_cells(game, []), "Select at least one")
    _assert_no_mutation(game, lambda: rules.flag_cells(game, ["R00C01", "R02C02"]), "revealed")
    _assert_no_mutation(game, lambda: rules.flag_cells(game, ["R99C99"]), "Unknown cell")


def test_revealing_last_safe_cell_wins_and_display_precedence_is_explicit():
    game = _manual_game(rows=2, cols=2, hazards={"R00C00"})

    rules.reveal_cells(game, ["R00C01"])
    rules.reveal_cells(game, ["R01C00"])
    result = rules.reveal_cells(game, ["R01C01"])

    assert result.ok is True
    assert game.state.status == "won"
    assert game.state.safe_revealed_count == 3
    assert game.cells["R00C01"].display_state == "won_safe"
    assert game.cells["R01C00"].display_state == "won_safe"
    assert game.cells["R01C01"].display_state == "won_safe"
    assert game.cells["R00C00"].display_state == "hidden"


def test_display_state_precedence_for_loss_and_flags():
    game = _manual_game(rows=3, cols=3, hazards={"R00C00", "R02C02"})
    rules.flag_cells(game, ["R00C01"])

    assert game.cells["R00C01"].display_state == "flagged"

    rules.reveal_cells(game, ["R00C00"])

    assert game.cells["R00C00"].display_state == "hazard_hit"
    assert game.cells["R02C02"].display_state == "hazard_revealed"
    assert game.cells["R00C01"].display_state == "flagged"
    assert game.cells["R01C02"].display_state == "hidden"


def test_golden_seed_2026_is_stable_for_demo_script():
    game = rules.new_game("Tiny Demo", seed=2026)
    hazards = sorted(cid for cid, cell in game.cells.items() if cell.is_hazard)

    assert hazards == ["R00C03", "R02C00", "R03C01", "R04C00"]
    assert game.cells["R00C00"].neighbor_count == 0
    assert game.cells["R00C02"].neighbor_count == 1

    safe_result = rules.reveal_cells(game, ["R00C00"])
    assert safe_result.ok is True
    assert game.cells["R00C00"].display_state == "revealed_empty"

    loss_result = rules.reveal_cells(game, ["R00C03"])
    assert loss_result.ok is True
    assert game.state.status == "lost"
    assert game.cells["R00C03"].display_state == "hazard_hit"


def _manual_game(rows, cols, hazards):
    ids = rules.generate_cell_ids(rows, cols)
    adjacency = rules.build_adjacency(rows, cols)
    counts = rules.compute_neighbor_counts(ids, hazards, adjacency)
    cells = {
        cid: rules.CellState(
            cell_id=cid,
            row_idx=int(cid[1:3]),
            col_idx=int(cid[4:6]),
            is_hazard=cid in hazards,
            neighbor_count=counts[cid],
        )
        for cid in ids
    }
    state = rules.GameState(
        mode="survey",
        status="playing",
        seed=1,
        board_rows=rows,
        board_cols=cols,
        hazard_count=len(hazards),
    )
    game = rules.SurveySweeperGame(cells=cells, adjacency=adjacency, state=state)
    rules.refresh_display_states(game)
    return game


def _assert_no_mutation(game, action, expected_message):
    before = copy.deepcopy(game)
    result = action()
    assert result.ok is False
    assert expected_message in result.message
    assert game == before
