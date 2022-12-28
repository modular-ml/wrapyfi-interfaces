import random
import logging

import pandas as pd
import matplotlib.pyplot as plt
from dtaidistance import dtw
from dtaidistance import dtw_visualisation as dtwvis
import numpy as np

df = pd.read_csv("results/benchmarking_orientation_interfaces__ros2,ros2_pitch.csv")
df_1 = df[df["topic"] == "orientation_waveshareimu"]
pitch_1 = df_1["pitch"].values
yaw_1 = df_1["yaw"].values
roll_1 = df_1["roll"].values

df_2 = df[df["topic"] == "orientation_sixdrepnet"]
pitch_2 = df_2["pitch"].values
yaw_2 = df_2["yaw"].values
roll_2 = df_2["roll"].values

x = np.arange(0, 300)
s1 = pitch_2
s2 = pitch_1

random.seed(1)


def plot_warpingpaths(s1, s2, paths, path=None, filename=None, shownumbers=False, showlegend=False,
                      figure=None, matshow_kwargs=None):
    """Plot the warping paths matrix.

    :param s1: Series 1
    :param s2: Series 2
    :param paths: Warping paths matrix
    :param path: Path to draw (typically this is the best path)
    :param filename: Filename for the image (optional)
    :param shownumbers: Show distances also as numbers
    :param showlegend: Show colormap legend
    :param figure: Matplotlib Figure object
    :return: Figure, Axes
    """
    try:
        from matplotlib import pyplot as plt
        from matplotlib import gridspec
        from matplotlib.ticker import FuncFormatter
    except ImportError:
        logging.error("The plot_warpingpaths function requires the matplotlib package to be installed.")
        return
    ratio = max(len(s1), len(s2))
    min_y = min(np.min(s1), np.min(s2))
    max_y = max(np.max(s1), np.max(s2))

    if figure is None:
        fig = plt.figure(figsize=(10, 10), frameon=True)
    else:
        fig = figure
    if showlegend:
        grows = 3
        gcols = 3
        height_ratios = [1, 6, 1]
        width_ratios = [1, 6, 1]
    else:
        grows = 2
        gcols = 2
        height_ratios = [1, 6]
        width_ratios = [1, 6]
    gs = gridspec.GridSpec(grows, gcols, wspace=1, hspace=1,
                           left=0, right=10.0, bottom=0, top=1.0,
                           height_ratios=height_ratios,
                           width_ratios=width_ratios)
    max_s2_x = np.max(s2)
    max_s2_y = len(s2)
    max_s1_x = np.max(s1)
    min_s1_x = np.min(s1)
    max_s1_y = len(s1)

    if path is None:
        p = dtw.best_path(paths)
    elif path == -1:
        p = None
    else:
        p = path

    def format_fn2_x(tick_val, tick_pos):
        return max_s2_x - tick_val

    def format_fn2_y(tick_val, tick_pos):
        return int(max_s2_y - tick_val)

    ax0 = fig.add_subplot(gs[0, 0])
    ax0.set_axis_off()
    if p is not None:
        ax0.text(0, 0, "Dist = {:.4f}".format(paths[p[-1][0] + 1, p[-1][1] + 1]))
    ax0.xaxis.set_major_locator(plt.NullLocator())
    ax0.yaxis.set_major_locator(plt.NullLocator())

    ax1 = fig.add_subplot(gs[0, 1])
    ax1.set_ylim([min_y, max_y])
    ax1.set_axis_off()
    ax1.xaxis.tick_top()
    # ax1.set_aspect(0.454)
    ax1.plot(range(len(s2)), s2, ".-")
    ax1.set_xlim([-0.7, len(s2) - 0.7])
    ax1.xaxis.set_major_locator(plt.NullLocator())
    ax1.yaxis.set_major_locator(plt.NullLocator())

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_xlim([-max_y, -min_y])
    ax2.set_axis_off()
    # ax2.set_aspect(0.8)
    # ax2.xaxis.set_major_formatter(FuncFormatter(format_fn2_x))
    # ax2.yaxis.set_major_formatter(FuncFormatter(format_fn2_y))
    ax2.xaxis.set_major_locator(plt.NullLocator())
    ax2.yaxis.set_major_locator(plt.NullLocator())
    ax2.plot(-s1, range(max_s1_y, 0, -1), ".-", lw=2, color="green")
    ax2.set_ylim([0.7, len(s1) + 0.7])

    ax3 = fig.add_subplot(gs[1, 1])
    # ax3.set_aspect(1)
    kwargs = {} if matshow_kwargs is None else matshow_kwargs
    img = ax3.matshow(paths[1:, 1:], **kwargs)
    # ax3.grid(which='major', color='w', linestyle='-', linewidth=0)
    # ax3.set_axis_off()
    if p is not None:
        py, px = zip(*p)
        ax3.plot(px, py, ".-", color="gray")
    # ax3.xaxis.set_major_locator(plt.NullLocator())
    # ax3.yaxis.set_major_locator(plt.NullLocator())
    if shownumbers:
        for r in range(1, paths.shape[0]):
            for c in range(1, paths.shape[1]):
                ax3.text(c - 1, r - 1, "{:.2f}".format(paths[r, c]))

    gs.tight_layout(fig, pad=1.0, h_pad=1.0, w_pad=1.0)
    # fig.subplots_adjust(hspace=0, wspace=0)

    if showlegend:
        # ax4 = fig.add_subplot(gs[0:, 2])
        ax4 = fig.add_axes([0.9, 0.25, 0.015, 0.5])
        fig.colorbar(img, cax=ax4)

    # Align the subplots:
    ax1pos = ax1.get_position().bounds
    ax2pos = ax2.get_position().bounds
    ax3pos = ax3.get_position().bounds
    ax2.set_position((ax2pos[0], ax2pos[1] + ax2pos[3] - ax3pos[3], ax2pos[2],
                      ax3pos[3]))  # adjust the time series on the left vertically
    if len(s1) < len(s2):
        ax3.set_position((ax3pos[0], ax2pos[1] + ax2pos[3] - ax3pos[3], ax3pos[2],
                          ax3pos[3]))  # move the time series on the left and the distance matrix upwards
        if showlegend:
            ax4pos = ax4.get_position().bounds
            ax4.set_position(
                (ax4pos[0], ax2pos[1] + ax2pos[3] - ax3pos[3], ax4pos[2], ax3pos[3]))  # move the legend upwards
    if len(s1) > len(s2):
        ax3.set_position((ax1pos[0], ax3pos[1], ax3pos[2],
                          ax3pos[3]))  # move the time series at the top and the distance matrix to the left
        ax1.set_position((ax1pos[0], ax1pos[1], ax3pos[2], ax1pos[3]))  # adjust the time series at the top horizontally
        if showlegend:
            ax4pos = ax4.get_position().bounds
            ax4.set_position((ax1pos[0] + ax3pos[2] + (ax1pos[0] - (ax2pos[0] + ax2pos[2])), ax4pos[1], ax4pos[2],
                              ax4pos[
                                  3]))  # move the legend to the left to equalize the horizontal spaces between the subplots
    if len(s1) == len(s2):
        ax1.set_position((ax3pos[0], ax1pos[1], ax3pos[2], ax1pos[3]))  # adjust the time series at the top horizontally

    ax = fig.axes

    if filename:
        if type(filename) != str:
            filename = str(filename)
        plt.savefig(filename)
        plt.close()
        fig, ax = None, None
    return fig, ax

d, paths = dtw.warping_paths(s1, s2, window=300, psi=2)
best_path = dtw.best_path(paths)
plot_warpingpaths(s1, s2, paths, best_path)

path = dtw.warping_path(s1, s2)
dtwvis.plot_warping(s1, s2, path, filename="results/warp.png")

plt.show()