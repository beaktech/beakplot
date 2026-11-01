import os
from pathlib import Path

# Keep renderer caches in the ignored local workspace on restricted machines.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".local/matplotlib"))
os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
import pytest


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")
