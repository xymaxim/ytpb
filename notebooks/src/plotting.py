import numpy as np
from brokenaxes import brokenaxes, BrokenAxes
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, MultipleLocator, ScalarFormatter


class PlainOffsetScalarFormatter(ScalarFormatter):
    def get_offset(self) -> str:
        assert not self.orderOfMagnitude
        if len(self.locs) == 0:
            return ""
        else:
            return f"{self.offset:+.0f}"


def plot_hat_graph(
    ax, sequences, y1, y2, width: float = 0.2, baseline: float | None = None
):
    if isinstance(ax, BrokenAxes):
        axt, axb = ax.axs
    else:
        axt, axb = ax, ax

    vl1 = ax.bar(
        x=sequences - width,
        height=0,
        bottom=y1,
        color="none",
        edgecolor="k",
        label="Ingestion-Walltime-Us",
        width=width * 2,
    )

    vl2 = ax.bar(
        x=sequences + width,
        height=y2 - y1,
        bottom=y1,
        color="C3",
        edgecolor="k",
        label="(Actual duration)",
        width=width * 2,
        lw=1,
    )

    if baseline:
        ax.axhline(baseline, ls=":", color="gray", lw=1, zorder=0)

    axt.xaxis.get_major_formatter().set_useOffset(False)
    axt.xaxis.get_major_formatter().set_scientific(False)

    axb.xaxis.set_major_locator(MaxNLocator(integer=True))
    axb.xaxis.set_major_formatter(PlainOffsetScalarFormatter())

    legend = ax.legend(frameon=False, ncol=1)

    legend_handles, legend_labels = axb.get_legend_handles_labels()
    legend_handles[0] = Line2D([], [], color="0.1")
    legend._legend_box = None
    legend._init_legend_box(legend_handles, legend_labels)
    legend._set_loc(legend._loc)
    legend.set_title(None)

    xaxis_margin = 0.5 + 0.2
    ax.set_xlim(sequences[0] - xaxis_margin, sequences[-1] - 1 + xaxis_margin)

    ax.set_xlabel("Sequence number, $N$")
    ax.set_ylabel("Duration as time difference, $t_{N + 1} - t_N$ (s)")


def plot_ingestion_line(
    ax,
    data,
    color,
    no_segment_boundaries: bool = False,
    label_length: int = 3,
    lw: int = 2,
):
    ingestion_values = data["Ingestion-Walltime-Us"]

    line_segments = []
    gap_segments = []
    duration_segments = []

    for sequence in data.index[:-1]:
        xs, ys = sequence, ingestion_values.loc[sequence]

        ingestion_diff = (
            ingestion_values.loc[sequence + 1] - ingestion_values.loc[sequence]
        )
        duration = data.loc[sequence]["duration"]

        if ingestion_diff > duration:
            xe, ye = sequence + 1, ingestion_values.loc[sequence + 1]
            gys = ingestion_values.loc[sequence] + duration
            gxs = np.interp(gys, ingestion_values, data.index)
            gap_segments.append([[gxs, gys], [xe, ye]])

            dye = ys + duration
            dxe = np.interp(dye, ingestion_values, data.index)
            duration_segments.append([[xs, ys], [dxe, dye]])
        else:
            xe, ye = sequence + 1, ingestion_values.loc[sequence + 1]
            line_segments.append([[xs, ys], [xe, ye]])

    linewidths = 2

    lc = LineCollection(
        line_segments,
        colors=["C0"],
        linewidths=linewidths,
        label="Nth difference, $d_i$ ($d_i \leq A_i$)",
    )
    ax.add_collection(lc)

    dlc = LineCollection(
        duration_segments,
        colors=["C3"],
        linewidths=linewidths,
        label="Actual duration, $A_i$ ($d_i > A_i$)",
    )
    ax.add_collection(dlc)

    glc = LineCollection(
        gap_segments,
        colors=["lightgray"],
        linewidths=linewidths,
        ls=(0, (4, 1)),
        label="Gap",
    )
    ax.add_collection(glc)

    if not no_segment_boundaries:
        ax.autoscale_view()
        for sequence in data.index[:-1]:
            xs, ys = sequence, ingestion_values.loc[sequence]
            _, ys_ax = ax.transLimits.transform((xs, ys))
            ax.plot(xs, ys, marker="|", ms=10, mew=1, color="k")

            x = sequence + 0.5
            y = np.interp(x, data.index, ingestion_values)

            p1 = (sequence, ingestion_values.loc[sequence])
            p2 = (sequence + 1, ingestion_values.loc[sequence + 1])
            rotation = np.rad2deg(np.arctan2(p2[1] - p1[1], p2[0] - p1[0]))

            ax.text(
                x,
                y,
                str(sequence)[-label_length:].lstrip("0") + "\n",
                ha="center",
                va="bottom",
                rotation=rotation,
                rotation_mode="anchor",
                transform_rotates_text=True,
                linespacing=0.75,
            )

    ax.spines.bottom.set_position(("axes", -0.05))

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(PlainOffsetScalarFormatter())

    ax.yaxis.set_major_formatter(PlainOffsetScalarFormatter())

    ax.set_xlabel("Sequence number, $N$")
    ax.set_ylabel("Ingestion-Walltime-Us (s)")
