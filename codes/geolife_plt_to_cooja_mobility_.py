!pip install pandas utm numpy
import os
import utm
import pandas as pd


INPUT_PLT = "/content/20070818042605.plt"               #  load Geolife data
NODE_ID    = 1                       #   Node number in Cooja
OUTPUT_FILE = "/content/cooja_mobility_single_node.txt"   # Use this file in  Cooja
TIME_STEP = 1000                     # each Point is 1 secound


#  read function  Geolife

def read_geolife_plt(file_path):
    data = []
    with open(file_path, 'r') as f:
        lines = f.readlines()[6:]   # remove line 1,2,3,4,5,6 in geolife_plt file

        for line in lines:
            parts = line.strip().split(',')
            lat = float(parts[0])
            lon = float(parts[1])
            data.append([lat, lon])

    return pd.DataFrame(data, columns=["lat", "lon"])

def convert_to_xy(df):
    xs = []
    ys = []
    for _, row in df.iterrows():
        x, y, _, _ = utm.from_latlon(row["lat"], row["lon"])
        xs.append(x)
        ys.append(y)
    df["x"] = xs
    df["y"] = ys
    return df


def generate_cooja_mobility(df, node_id, output_file, step=TIME_STEP):
    with open(output_file, "w") as f:
        t = 0
        f.write(f"# Node {node_id} trajectory (from {INPUT_PLT})\n") # Add a header for clarity
        for _, row in df.iterrows():
            # Cooja format: $time $nodeID $x $y 0
            f.write(f"{t} {node_id} {row['x']:.2f} {row['y']:.2f} 0\n")
            t += step
    print("Mobility file generated:", output_file)

# run
df = read_geolife_plt(INPUT_PLT)
df = convert_to_xy(df)
generate_cooja_mobility(df, NODE_ID, OUTPUT_FILE)