

def str_or_int(arg):
  try:
    return int(arg)  # try convert to int
  except ValueError:
    return arg


def cartesian_to_spherical(xyz):
  import numpy as np
  ptr = np.zeros((3,))
  xy = xyz[0] ** 2 + xyz[1] ** 2
  ptr[0] = np.arctan2(xyz[1], xyz[0])
  ptr[1] = np.arctan2(xyz[2], np.sqrt(xy)) # for elevation angle defined from XY-plane up
  # ptr[1] = np.arctan2(np.sqrt(xy), xyz[2])  # for elevation angle defined from Z-axis down
  ptr[2] = np.sqrt(xy + xyz[2] ** 2)
  return ptr
  

def mode_smoothing_filter(time_series, alpha=0.22, beta=0.1, window_length=7):
  import scipy.stats
  #behave = ["stand", "stand", "stand", "stand", "lying", "lying", "eating"]
  most_freq_val = lambda x: scipy.stats.mode(x)[0][0]
  smoothed = [most_freq_val(time_series[i:i + window_length]) for i in range(0, len(time_series) - window_length + 1)][-1]
  return smoothed
