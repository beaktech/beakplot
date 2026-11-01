"""Create repeatable example detections and charts; no real input is read.

Run from an installed checkout: python examples/generate.py
All outputs go to ignored .local/examples by default.
"""

import argparse
import csv
from datetime import date, timedelta
import math
from pathlib import Path
import random

from beakplot import sun_times
from beakplot.cli import main


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    source = output / "synthetic.csv"
    random_source = random.Random(42)
    start, end = date(2025, 7, 1), date(2025, 11, 5)
    identity = 0
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "time", "scientific_name", "detection_id", "confidence"])
        for i in range((end - start).days + 1):
            day = start + timedelta(days=i)
            if i in (40, 41, 72, 97):
                continue  # Synthetic recording gaps: unknown, not zero.
            identity += 1
            writer.writerow([day, "12:00:00", "Turdus merula", identity, .9])
            if i % 23 == 0:
                continue  # Other species recorded: a genuine zero for the robin.
            rise, sunset = sun_times(day, 54.6, -3.13, "Europe/London")
            amplitude = (5 + i / 5) * random_source.uniform(.65, 1.25)
            for slot in range(96):
                hour = (slot + .5) / 4
                morning = math.exp(-.5 * ((hour - rise - .25) / .38) ** 2)
                evening = .45 * math.exp(-.5 * ((hour - sunset + .5) / .32) ** 2)
                count = round(amplitude * (morning + evening))
                for _ in range(count):
                    identity += 1
                    writer.writerow([day, f"{slot // 4:02}:{slot % 4 * 15:02}:00",
                                     "Erithacus rubecula", identity, .9])
    for extension in ("svg", "png"):
        for command, title, options in (
                ("heatmap", "European Robin — synthetic heatmap",
                 ["--lat", "54.6", "--lon", "-3.13", "--vmax", "40"]),
                ("daily", "European Robin — synthetic daily counts", ["--label", "Synthetic station"])):
            status = main([command, "--csv", str(source), "--species", "Robin",
                           "--tz", "Europe/London", "--from", str(start), "--to", str(end),
                           "--include-partial", "--title", title, "--out", str(output / f"{command}.{extension}"),
                           *options])
            if status:
                raise RuntimeError(f"Could not draw the synthetic {command} example")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".local/examples"))
    generate(parser.parse_args().out)
