#!/usr/bin/env python3
import csv
from pathlib import Path

GEO_FILES = {
    1: "node01.plt",
    2: "node02.plt",
    # ...
    # 50: "node50.plt",
}

OUTPUT_CSV = "mobility.csv"
X_MIN, X_MAX = 0.0, 1000.0
Y_MIN, Y_MAX = 0.0, 1000.0


def read_geolife_trajectory(path: Path):
    points = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                lat = float(parts[0])
                lon = float(parts[1])
            except ValueError:
                continue
            points.append((lat, lon))
    return points


def normalize_coords(all_trajs):
    lats = [lat for traj in all_trajs.values() for (lat, _) in traj]
    lons = [lon for traj in all_trajs.values() for (_, lon) in traj]

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    def norm(lat, lon):
        x = (lat - lat_min) / (lat_max - lat_min + 1e-9)
        y = (lon - lon_min) / (lon_max - lon_min + 1e-9)
        x = X_MIN + x * (X_MAX - X_MIN)
        y = Y_MIN + y * (Y_MAX - Y_MIN)
        return x, y

    return norm


def main():
    base = Path(".").resolve()

    all_trajs = {}
    for node_id, filename in GEO_FILES.items():
        path = base / filename
        traj = read_geolife_trajectory(path)
        if not traj:
            print(f"WARNING: empty trajectory for node {node_id} ({filename})")
        all_trajs[node_id] = traj

    if not all_trajs:
        print("No trajectories found. Please fill GEO_FILES mapping.")
        return

    norm = normalize_coords(all_trajs)

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "node_id", "x", "y"])
        for node_id, traj in all_trajs.items():
            for t, (lat, lon) in enumerate(traj):
                x, y = norm(lat, lon)
                writer.writerow([t, node_id, x, y])

    print(f"Wrote mobility file: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
