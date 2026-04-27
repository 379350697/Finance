def moving_average(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def volume_average(values: list[float], window: int) -> float | None:
    return moving_average(values, window)
