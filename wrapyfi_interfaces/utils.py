def cartesian_to_spherical(xyz):
  import numpy as np
  ptr = np.zeros((3,))
  xy = xyz[0] ** 2 + xyz[1] ** 2
  ptr[0] = np.arctan2(xyz[1], xyz[0])
  ptr[1] = np.arctan2(xyz[2], np.sqrt(xy)) # for elevation angle defined from XY-plane up
  # ptr[1] = np.arctan2(np.sqrt(xy), xyz[2])  # for elevation angle defined from Z-axis down
  ptr[2] = np.sqrt(xy + xyz[2] ** 2)
  return ptr
  

def exponential_smoothing_filter(time_series, alpha=0.22, beta=0.1):
  # TODO (fabawi): create smoothing filter
  pass
