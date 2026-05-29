import matplotlib.pyplot as plt
import numpy as np

from matplotlib.widgets import Button, Slider


# Sheperd approximation
def f(t_sec, E, K, Q_mah, I_ma, A, B):

    # Convert to the right units
    Q = Q_mah / 1000.0  # mAh -> Ah
    I = I_ma / 1000.0  # mA -> A
    it = I * (t_sec / 3600.0)

    # Safety for div0
    it = np.minimum(it, Q * 0.99)

    return E - K * (Q / (Q - it)) * it + A * np.exp(-B * it)


# Define initial parameters
init_E = 3.73
init_K = 0.1
init_Q = 1000.0  # 1000 mAh
init_I = 500.0  # 500 mA
init_A = 0.35
init_B = 25

# Get the maximal discharge time to fit the plot
t_max = (init_Q / init_I) * 3600.0
t = np.linspace(0, t_max, 5000)

# Create the figure and the line that we will manipulate
fig, ax = plt.subplots(figsize=(10, 6))

# Initial plot
V_batt = f(t, init_E, init_K, init_Q, init_I, init_A, init_B)
(line,) = ax.plot(t / 3600.0, V_batt, lw=2, color="b")

ax.set_xlabel("Time [h]")
ax.set_ylabel("Voltage [V]")
ax.set_title("Simulated battery model (Shepherd)")
ax.grid(True, linestyle=":")
ax.set_ylim(2.5, 4.3)

# adjust the main plot to make room for the sliders
fig.subplots_adjust(left=0.25, bottom=0.25)

# Add the sliders
axcurr = fig.add_axes([0.25, 0.15, 0.65, 0.03])
current_slider = Slider(
    ax=axcurr,
    label="Courant [mA]",
    valmin=0,
    valmax=4000,
    valinit=init_I,
)

axa = fig.add_axes([0.25, 0.1, 0.65, 0.03])
a_slider = Slider(
    ax=axa,
    label="Overvoltage (A) [V]",
    valmin=0,
    valmax=2,
    valinit=init_A,
)

axb = fig.add_axes([0.25, 0.05, 0.65, 0.03])
b_slider = Slider(
    ax=axb,
    label="Droop (B) [V]",
    valmin=0,
    valmax=50,
    valinit=init_B,
)

axcap = fig.add_axes([0.05, 0.25, 0.0225, 0.63])
batt_slider = Slider(
    ax=axcap,
    label="Capacity [mAh]",
    valmin=1,
    valmax=5000,
    valinit=init_Q,
    orientation="vertical",
)

axe = fig.add_axes([0.1, 0.25, 0.0225, 0.63])
e_slider = Slider(
    ax=axe,
    label="Typical Voltage (E) [V]",
    valmin=0,
    valmax=20,
    valinit=init_E,
    orientation="vertical",
)

axk = fig.add_axes([0.15, 0.25, 0.0225, 0.63])
k_slider = Slider(
    ax=axk,
    label="Factor K [??]",
    valmin=0,
    valmax=2,
    valinit=init_K,
    orientation="vertical",
)


# The function to be called anytime a slider's value changes
def update(val):
    current_t_max = (batt_slider.val / current_slider.val) * 3600.0
    global t
    t = np.linspace(0, current_t_max, 1000)

    line.set_xdata(t / 3600.0)
    line.set_ydata(
        f(
            t,
            e_slider.val,
            k_slider.val,
            batt_slider.val,
            current_slider.val,
            a_slider.val,
            b_slider.val,
        )
    )

    # Adjust limits
    ax.set_xlim(0, current_t_max / 3600.0)
    ax.set_ylim(2.0, max(4.5, e_slider.val + a_slider.val + 0.2))

    # Draw
    fig.canvas.draw_idle()


# register the update function with each slider
batt_slider.on_changed(update)
current_slider.on_changed(update)
a_slider.on_changed(update)
b_slider.on_changed(update)
e_slider.on_changed(update)
k_slider.on_changed(update)


plt.show()
