
def mode_smoothing_filter(time_series, alpha=0.22, beta=0.1, window_length=6):
    # TODO (fabawi): consider level and trend for smoothing
    import scipy.stats
    # behave = ["stand", "stand", "stand", "stand", "lying", "lying", "eating"]
    most_freq_val = lambda x: scipy.stats.mode(x)[0][0]
    smoothed = [most_freq_val(time_series[i:i + min(len(time_series), window_length)]) for i in range(0, len(time_series) - min(len(time_series), window_length) + 1)][-1]
    return smoothed
