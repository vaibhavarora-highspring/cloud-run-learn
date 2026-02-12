from deploy_app.main import calculate_health_score


def test_health_score_excellent():
    score = calculate_health_score(
        cpu_percent=10,
        memory_percent=20,
        uptime_seconds=4000
    )
    assert score >= 85


def test_health_score_high_cpu():
    score = calculate_health_score(
        cpu_percent=95,
        memory_percent=30,
        uptime_seconds=100
    )
    assert score < 60


def test_health_score_high_memory():
    score = calculate_health_score(
        cpu_percent=20,
        memory_percent=95,
        uptime_seconds=100
    )
    assert score < 60


def test_health_score_never_negative():
    score = calculate_health_score(
        cpu_percent=100,
        memory_percent=100,
        uptime_seconds=0
    )
    assert score >= 0


def test_health_score_never_above_100():
    score = calculate_health_score(
        cpu_percent=0,
        memory_percent=0,
        uptime_seconds=100000
    )
    assert score <= 100