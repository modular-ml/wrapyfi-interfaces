
def cartesian_to_spherical(xyz=None, x=None, y=None, z=None, expand_return=None):
    from operator import xor
    import numpy as np

    assert xor((xyz is not None), all((x is not None, y is not None, z is not None)))

    if expand_return is None:
        expand_return = False if xyz is None else True
    if xyz is None:
        xyz = (x, y, z)

    ptr = np.zeros((3,))
    xy = xyz[0] ** 2 + xyz[1] ** 2
    ptr[0] = np.arctan2(xyz[1], xyz[0])
    ptr[1] = np.arctan2(xyz[2], np.sqrt(xy)) # for elevation angle defined from XY-plane up
    # ptr[1] = np.arctan2(np.sqrt(xy), xyz[2])  # for elevation angle defined from Z-axis down
    ptr[2] = np.sqrt(xy + xyz[2] ** 2)
    return ptr if not expand_return else {"p": ptr[0], "t": ptr[1], "r": ptr[2]}


def euler_to_quaternion(euler=None, pitch=None, roll=None, yaw=None, order="xyz", expand_return=None):
    from operator import xor
    import numpy as np
    from scipy.spatial.transform import Rotation

    assert xor((euler is not None), all((pitch is not None, roll is not None, yaw is not None)))

    if expand_return is None:
        expand_return = False if euler is None else True
    if euler is None:
        _order = order.lower()
        if _order == "xyz":
            euler = (roll, pitch, yaw)
        elif _order == "xzy":
            euler = (roll, yaw, pitch)
        elif _order == "yxz":
            euler = (pitch, roll, yaw)
        elif _order == "yzx":
            euler = (pitch, yaw, roll)
        elif _order == "zxy":
            euler = (pitch, roll, yaw)
        elif _order == "zyx":
            euler = (pitch, yaw, roll)

    rot = Rotation.from_euler(order, euler, degrees=True)
    rot_quat = rot.as_quat()
    return rot_quat if not expand_return else {"quat_x": rot_quat[0],
                                               "quat_y": rot_quat[1],
                                               "quat_z": rot_quat[2],
                                               "quat_w": rot_quat[3],
                                               "order": order}


def quaternion_to_euler(quaternion=None, quat_x=None, quat_y=None, quat_z=None, quat_w=None, order="xyz", expand_return=None):
    from operator import xor
    from scipy.spatial.transform import Rotation

    assert xor((quaternion is not None), all((quat_x is not None, quat_y is not None,
                                              quat_z is not None, quat_w is not None)))

    if expand_return is None:
        expand_return = False if quaternion is None else True

    rot = Rotation.from_quat(quaternion)
    euler = rot.as_euler(order, degrees=True)
    if not expand_return:
        return euler
    else:
        _order = order.lower()
        if _order == "xyz":
            euler = {"roll": euler[0], "pitch": euler[1], "yaw": euler[2]}
        elif _order == "xzy":
            euler = {"roll": euler[0], "pitch": euler[2], "yaw": euler[1]}
        elif _order == "yxz":
            euler = {"roll": euler[1], "pitch": euler[0], "yaw": euler[2]}
        elif _order == "yzx":
            euler = {"roll": euler[2], "pitch": euler[0], "yaw": euler[1]}
        elif _order == "zxy":
            euler = {"roll": euler[1], "pitch": euler[2], "yaw": euler[0]}
        elif _order == "zyx":
            euler = {"roll": euler[2], "pitch": euler[1], "yaw": euler[0]}
        euler.update(order=order)
        return euler
