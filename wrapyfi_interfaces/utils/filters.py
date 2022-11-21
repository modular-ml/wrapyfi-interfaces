
def mode_smoothing_filter(time_series, default, alpha=0.22, beta=0.1, window_length=6, min_count=None):
    # TODO (fabawi): consider level and trend for smoothing
    import scipy.stats
    if min_count is None:
        min_count = window_length // 2
    mode = scipy.stats.mode(time_series[-window_length:])
    return mode.mode[0] if mode.count >= min_count else default
