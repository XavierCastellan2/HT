import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

class TrainingGraph(ttk.Frame):
    """A Tkinter widget that displays a real-time matplotlib graph."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212, sharex=self.ax1)

        self.ax1.set_title("Power")
        self.ax1.set_ylabel("Watts")
        self.ax2.set_title("Heart Rate & Cadence")
        self.ax2.set_ylabel("BPM / RPM")
        self.ax2.set_xlabel("Time (s)")

        # Hide x-axis labels on the top plot
        self.ax1.tick_params(axis='x', labelbottom=False)

        self.series = {
            "target_power": self.ax1.plot([], [], label="Target Power (W)", linestyle='--')[0],
            "power": self.ax1.plot([], [], label="Realized Power (W)")[0],
            "hr": self.ax2.plot([], [], label="Heart Rate (BPM)")[0],
            "cadence": self.ax2.plot([], [], label="Cadence (RPM)")[0],
        }

        self.ax1.legend()
        self.ax2.legend()
        self.ax1.grid(True)
        self.ax2.grid(True)
        self.figure.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.figure, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def add_data_point(self, series_name, x, y):
        """Adds a new data point to a named series."""
        line = self.series.get(series_name)
        if line:
            line.set_data(np.append(line.get_xdata(), x), np.append(line.get_ydata(), y))

    def set_time_axis_range(self, total_time: int):
        """Sets the x-axis limit to a fixed value."""
        self.ax1.set_xlim(0, total_time)
        self.ax2.set_xlim(0, total_time)
        self.draw_plot()

    def draw_plot(self):
        """Redraws the plot, autoscaling the y-axes only."""
        self.ax1.relim()
        self.ax1.autoscale_view(scalex=False, scaley=True)
        self.ax2.relim()
        self.ax2.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw()

    def clear_plot(self):
        """Clears all data from the plot."""
        for line in self.series.values():
            line.set_data([], [])
        # Reset axes to autoscale again on the next run
        self.ax1.autoscale_view(True, True, True)
        self.ax2.autoscale_view(True, True, True)
        self.draw_plot()
