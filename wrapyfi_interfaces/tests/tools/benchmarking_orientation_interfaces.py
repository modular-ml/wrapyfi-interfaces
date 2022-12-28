import argparse
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import pandas as pd

from wrapyfi.connect.wrapper import MiddlewareCommunicator


SHOULD_WAIT = True

parser = argparse.ArgumentParser()
parser.add_argument("--mwares", type=str, default=["ros2", "ros2"],
                    choices=MiddlewareCommunicator.get_communicators(), nargs="+",
                    help="The middlewares to use for reception of IMU and Model data")
parser.add_argument("--ports", type=str,
                    default=["/control_interface/orientation_waveshareimu",
                             "/control_interface/orientation_sixdrepnet"], nargs="+",
                    help="The ports to use for reception of IMU and Model data")
parser.add_argument("--trials", type=int, default=300, help="Number of trials to run per middleware")
parser.add_argument("--skip_trials", type=int, default=0, help="Number of trials to skip before logging "
                                                               "to csv to avoid warmup time logging")
args = parser.parse_args()


class Benchmarker(MiddlewareCommunicator):

    @MiddlewareCommunicator.register("NativeObject", "$_orientation_1_mware", "Benchmarker", "$orientation_1_port",
                                     carrier="tcp", should_wait=SHOULD_WAIT)
    @MiddlewareCommunicator.register("NativeObject", "$_orientation_2_mware", "Benchmarker", "$orientation_2_port",
                                     carrier="tcp", should_wait=SHOULD_WAIT)
    def receive_orientations(self, orientation_1_port, orientation_2_port, _orientation_1_mware, _orientation_2_mware):
        return None, None

counter = 0
benchmarker = Benchmarker()
benchmark_logger = pd.DataFrame(columns=["middleware", "timestamp", "delay", "pitch", "roll", "yaw", "count"])
benchmark_iterator = {}

benchmarker.activate_communication(benchmarker.receive_orientations, mode="listen")

fig, (ax1, ax2, ax3) = plt.subplots(3, 1)
plt.xlabel('steps')

plotlays, plotcols = [2], ["black", "red"]
lines_pitch, lines_yaw, lines_roll = [], [], []
for index in range(2):
    lobj = ax1.plot([], [], lw=2, color=plotcols[index])[0]
    lines_pitch.append(lobj)
for index in range(2):
    lobj = ax2.plot([], [], lw=2, color=plotcols[index])[0]
    lines_yaw.append(lobj)
for index in range(2):
    lobj = ax3.plot([], [], lw=2, color=plotcols[index])[0]
    lines_roll.append(lobj)

x1_pitch, y1_pitch = deque(maxlen=200), deque(maxlen=200)
x2_pitch, y2_pitch = deque(maxlen=200), deque(maxlen=200)
x1_yaw, y1_yaw = deque(maxlen=200), deque(maxlen=200)
x2_yaw, y2_yaw = deque(maxlen=200), deque(maxlen=200)
x1_roll, y1_roll = deque(maxlen=200), deque(maxlen=200)
x2_roll, y2_roll = deque(maxlen=200), deque(maxlen=200)

lines = [lines_pitch[0], lines_pitch[1], lines_yaw[0], lines_yaw[1], lines_roll[0], lines_roll[1]]

def init():
    ax1.set_ylim(-80, 80)
    ax1.set_xlim(0, 200)
    ax1.set_ylabel('pitch')
    ax1.grid()
    ax2.set_ylim(-80, 80)
    ax2.set_xlim(0, 200)
    ax2.set_ylabel('yaw')
    ax2.grid()
    ax3.set_ylim(-80, 80)
    ax3.set_xlim(0, 200)
    ax3.set_ylabel('roll')
    ax3.grid()
    for line in lines:
        line.set_data([], [])
    return lines


def update(frame):
    global counter, benchmark_logger
    orientation_1_data, orientation_2_data = benchmarker.receive_orientations(
        orientation_1_port=args.ports[0], orientation_2_port=args.ports[1],
        _orientation_1_mware=args.mwares[0], _orientation_2_mware=args.mwares[1])
    curr_time = time.time()

    if orientation_1_data is not None:
        orientation_1_data.update(delay=curr_time - orientation_1_data["timestamp"],
                                  middleware=args.mwares[0],
                                  count=counter)
        if counter > args.skip_trials:
            orientation_1_dataframe = pd.DataFrame([orientation_1_data])
            benchmark_logger = pd.concat([benchmark_logger, orientation_1_dataframe], ignore_index=True)

        x1_pitch.append(counter)
        y1_pitch.append(orientation_1_data['pitch'])
        lines[0].set_data(range(len(list(x1_pitch))), list(y1_pitch))

        x1_yaw.append(counter)
        y1_yaw.append(orientation_1_data['yaw'])
        lines[2].set_data(range(len(list(x1_yaw))), list(y1_yaw))

        x1_roll.append(counter)
        y1_roll.append(orientation_1_data['roll'])
        lines[4].set_data(range(len(list(x1_roll))), list(y1_roll))

        if orientation_2_data is None:
            x2_pitch.append(counter)
            y2_pitch.append(None)
            lines[1].set_data(range(len(list(x2_pitch))), list(y2_pitch))

            x2_yaw.append(counter)
            y2_yaw.append(None)
            lines[3].set_data(range(len(list(x2_yaw))), list(y2_yaw))

            x2_roll.append(counter)
            y2_roll.append(None)
            lines[5].set_data(range(len(list(x2_roll))), list(y2_roll))


    if orientation_2_data is not None:
        orientation_2_data.update(delay=curr_time - orientation_2_data["timestamp"],
                                  middleware=args.mwares[1],
                                  count=counter)
        if counter > args.skip_trials:
            orientation_2_dataframe = pd.DataFrame([orientation_2_data])
            benchmark_logger = pd.concat([benchmark_logger, orientation_2_dataframe], ignore_index=True)

        x2_pitch.append(counter)
        y2_pitch.append(orientation_2_data['pitch'])
        lines[1].set_data(range(len(list(x2_pitch))), list(y2_pitch))

        x2_yaw.append(counter)
        y2_yaw.append(orientation_2_data['yaw'])
        lines[3].set_data(range(len(list(x2_yaw))), list(y2_yaw))

        x2_roll.append(counter)
        y2_roll.append(orientation_2_data['roll'])
        lines[5].set_data(range(len(list(x2_roll))), list(y2_roll))

        if orientation_1_data is None:
            x1_pitch.append(counter)
            y1_pitch.append(None)
            lines[0].set_data(range(len(list(x1_pitch))), list(y1_pitch))

            x1_yaw.append(counter)
            y1_yaw.append(None)
            lines[2].set_data(range(len(list(x1_yaw))), list(y1_yaw))

            x1_roll.append(counter)
            y1_roll.append(None)
            lines[4].set_data(range(len(list(x1_roll))), list(y1_roll))

    if orientation_2_data is not None or orientation_1_data is not None:
        counter += 1

    return lines


orientation_1_data, orientation_2_data = None, None
time1, pitch1, roll1, yaw1 = [], [], [], []
time2, pitch2, roll2, yaw2 = [], [], [], []

ani = FuncAnimation(fig, update, frames=args.trials, interval=30, init_func=init, blit=True, repeat=False)
plt.show()

benchmark_logger.to_csv(f"results/benchmarking_orientation_interfaces__{','.join(args.mwares)}.csv", index=False)