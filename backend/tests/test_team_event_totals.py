import uuid
from types import SimpleNamespace

from app.schemas.matches import TeamStatsResponse
from app.services.matches import apply_event_totals


def test_team_totals_count_each_shot_once_and_leave_fouls_unknown() -> None:
    team_id = uuid.uuid4()
    player = SimpleNamespace(id=uuid.uuid4(), team=SimpleNamespace(id=team_id))
    analytics = SimpleNamespace(
        team_id=team_id,
        events=[
            SimpleNamespace(event_type="shot", title="Possible shot · xG 0.42"),
            SimpleNamespace(event_type="shot_on_target", title="Possible shot on target · xG 0.42"),
            SimpleNamespace(event_type="big_chance", title="Possible big chance · xG 0.42"),
            SimpleNamespace(event_type="successful_pass", title="Possible successful pass"),
            SimpleNamespace(event_type="failed_pass", title="Possible failed pass"),
            SimpleNamespace(event_type="tackle", title="Possible tackle"),
            SimpleNamespace(event_type="interception", title="Possible interception"),
            SimpleNamespace(event_type="corner", title="Possible corner"),
            SimpleNamespace(event_type="save", title="Possible save"),
            SimpleNamespace(event_type="goal_kick", title="Possible goal kick"),
            SimpleNamespace(event_type="woodwork", title="Possible woodwork"),
        ],
    )
    measured = [TeamStatsResponse(team_id=team_id)]
    apply_event_totals(measured, [player], {player.id: analytics}, True)
    assert measured[0].shots == 1
    assert measured[0].shots_on_target == 1
    assert measured[0].xg == 0.42
    assert measured[0].big_chances == 1
    assert measured[0].passes == 2
    assert measured[0].accurate_passes == 1
    assert measured[0].tackles == 1
    assert measured[0].interceptions == 1
    assert measured[0].corners == 1
    assert measured[0].saves == 1
    assert measured[0].goal_kicks == 1
    assert measured[0].woodwork == 1
    assert measured[0].fouls is None

    unknown = [TeamStatsResponse(team_id=team_id)]
    apply_event_totals(unknown, [player], {player.id: analytics}, False)
    assert unknown[0].shots is None
    assert unknown[0].goals is None
    assert unknown[0].xg is None
    assert unknown[0].passes == 2
    assert unknown[0].accurate_passes == 1
    assert unknown[0].tackles == 1
    assert unknown[0].interceptions == 1
    assert unknown[0].fouls is None
