import os
import pandas as pd

def save_points(csv_file, image_name, points_to_save, sender=None, save_button=None):
    """
    Save image points (and optional world coordinates) to a CSV file.

    Args:
        csv_file (str): Path to the CSV file.
        image_name (str): Current image name.
        points_to_save (list of dict): List of points, each with keys:
            - "points": point number (int)
            - "xi", "yi": image coordinates (float)
            - "xw", "yw": optional world coordinates (float)
        sender: the Qt sender (optional, used to detect manual save).
        save_button: reference to SaveSetPnt button (optional).
    """
    if not points_to_save:
        return

    # Create DataFrame with new points
    new_rows = pd.DataFrame(points_to_save)

    # Load existing data or create new
    if os.path.exists(csv_file):
        try:
            existing_df = pd.read_csv(csv_file)
            # Remove existing entries for this image
            existing_df = existing_df[existing_df['image_name'] != image_name]
            # Combine
            df = pd.concat([existing_df, new_rows], ignore_index=True)
        except Exception as e:
            print(f"[io_utils] Error reading existing CSV: {e}")
            df = new_rows
    else:
        df = new_rows

    # Save to CSV
    try:
        df.to_csv(csv_file, index=False)
        # Verbose output only for manual saves
        if sender is not None and save_button is not None and sender == save_button:
            print(f"Saved {len(points_to_save)} points for '{image_name}' → {csv_file}")
            for pt in points_to_save:
                xw = pt.get("xw", "None")
                yw = pt.get("yw", "None")
                print(f"  Point {pt['points']}: Image({pt['xi']}, {pt['yi']}), World({xw}, {yw})")
        else:
            print(f"Auto-saved {len(points_to_save)} points for '{image_name}'")
    except Exception as e:
        print(f"[io_utils] Error saving to CSV: {e}")
