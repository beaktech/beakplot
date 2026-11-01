"""Shared chart appearance, adapted from the original seasonal figures."""

from functools import wraps

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

DEFAULT_SUBTITLE = "Detections are automatic identifications, not individual birds."
STYLE = {
    'font.family': ['DejaVu Sans', 'sans-serif'], 'font.size': 12,
    'svg.fonttype': 'none', 'svg.hashsalt': 'dayclock',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.spines.left': False, 'axes.edgecolor': '#cbd4dc',
    'text.color': '#33465e', 'axes.labelcolor': '#33465e',
    'xtick.color': '#33465e', 'ytick.color': '#33465e',
}


def styled(draw):
    """Apply chart defaults without changing the caller's global settings."""
    @wraps(draw)
    def wrapper(*args, **kwargs):
        with plt.rc_context(STYLE):
            return draw(*args, **kwargs)
    return wrapper


def add_logo(fig, logo, height=26, margin=12):
    """Optional image in the bottom-right corner, a fixed size in points."""
    if logo is None:
        return
    image = mpimg.imread(logo)
    w_in, h_in = fig.get_size_inches()
    h = height / 72 / h_in
    w = height * image.shape[1] / image.shape[0] / 72 / w_in
    ax = fig.add_axes([1 - margin / 72 / w_in - w, margin / 72 / h_in, w, h])
    ax.imshow(image)
    ax.axis('off')


def from_top(fig, points):
    """Place header rows using consistent physical spacing on every figure size."""
    return 1 - points / (72 * fig.get_figheight())
