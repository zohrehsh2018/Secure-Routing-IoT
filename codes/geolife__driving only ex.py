import os
import pandas as pd
import datetime

DATASET_ROOT = '/content/sample_data/Untitled Folder'
OUTPUT_FILE = 'geolife_cars.csv'

def parse_plt(plt_path):
    try:
        df = pd.read_csv(plt_path, skiprows=6, header=None,
                         names=['lat', 'lon', 'zero', 'alt', 'days', 'date', 'time'])

        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        return df[['lat', 'lon', 'timestamp']]
    except Exception as e:
        return None

def extract_car_trajectories():
    all_car_points = []

    users = [d for d in os.listdir(DATASET_ROOT) if os.path.isdir(os.path.join(DATASET_ROOT, d))]

    print(f"Found {len(users)} users. Scanning for car/taxi labels...")

    for user in users:
        user_dir = os.path.join(DATASET_ROOT, user)
        labels_path = os.path.join(user_dir, 'labels.txt')

        if not os.path.exists(labels_path):
            continue

        try:
            labels = pd.read_csv(labels_path, sep='\t', header=0)
            car_labels = labels[labels['Transportation Mode'].isin(['car', 'taxi'])]

            if car_labels.empty:
                continue

            print(f"Processing User {user}: Found {len(car_labels)} car trips.")

            car_labels['Start Time'] = pd.to_datetime(car_labels['Start Time'])
            car_labels['End Time'] = pd.to_datetime(car_labels['End Time'])

            traj_dir = os.path.join(user_dir, 'Trajectory')
            for plt_file in os.listdir(traj_dir):
                if not plt_file.endswith('.plt'): continue

                plt_path = os.path.join(traj_dir, plt_file)
                traj_df = parse_plt(plt_path)

                if traj_df is None: continue

                for _, row in car_labels.iterrows():
                    mask = (traj_df['timestamp'] >= row['Start Time']) & \
                           (traj_df['timestamp'] <= row['End Time'])

                    filtered_points = traj_df[mask].copy()

                    if not filtered_points.empty:
                        filtered_points['user_id'] = user
                        filtered_points['mode'] = row['Transportation Mode']
                        all_car_points.append(filtered_points)

        except Exception as e:
            print(f"Error processing user {user}: {e}")

    if all_car_points:
        final_df = pd.concat(all_car_points)
        final_df.to_csv(OUTPUT_FILE, index=False)
        print(f"Done! Saved {len(final_df)} points to {OUTPUT_FILE}")
    else:
        print("No car trajectories found.")

if __name__ == "__main__":
    extract_car_trajectories()