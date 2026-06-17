# Camera Calibration UI Usage Guide

## Overview

This project provides two PyQt5 desktop tools:

1. `main.py`
   Main calibration UI with:
   Tab 1 for intrinsic calibration
   Tab 2 for extrinsic calibration
2. `calibration_val/main.py`
   Standalone validation UI for checking image points against expected world coordinates

## Before You Start

- Install dependencies from `requirements.txt`
- Connect your camera before launching the UI
- Prepare a folder for each camera you want to calibrate

Recommended per-camera folder layout:

```text
Camera_1/
  camera_data/
  intrinsic_images/
  extrinsic_images/
  points.csv
```

The application creates missing folders such as `camera_data/`, `intrinsic_images/`, `extrinsic_images/`, and `points.csv` when needed.

## Run The Main UI

```bash
python3 main.py
```

## Main UI Workflow

The main UI has two tabs:

- Tab 1: Intrinsic calibration
- Tab 2: Extrinsic calibration

Use Tab 1 first. Use Tab 2 after intrinsic calibration files have been saved into `camera_data/`.

## Tab 1: Intrinsic Calibration

Purpose:
Estimate the camera intrinsics and lens distortion from checkerboard images.

### Tab 1 Steps

1. Select a camera from `Available Cameras`
2. Choose a base save folder when prompted
3. Capture several checkerboard images with `Take a Picture`
4. Confirm the images appear in the image list
5. Choose the checkerboard size from the dropdown
6. Click `Intrinsic Calibrate`

### Tab 1 Notes

- The selected base folder is used to create or reuse:
  `intrinsic_images/`
  `camera_data/`
- Captured images are stored in `intrinsic_images/`
- The UI displays the selected or latest captured image
- During calibration, checkerboard corners are detected on each image
- Images where the checkerboard is not detected can be removed from disk and from the UI list
- At least 3 valid checkerboard images are required for calibration

### Tab 1 Output Files

Saved in `camera_data/`:

- `camera_matrix.npy`
- `distortion_coeff.npy`
- `new_camera_matrix.npy`
- `roi.npy`

## Tab 2: Extrinsic Calibration

Purpose:
Estimate the camera pose relative to the world plane using measured point correspondences.

### Tab 2 Steps

1. Select a camera from `Available Camera`
2. Choose a base save folder when prompted
3. Click `Camera View` if needed
4. Capture an image with `Take a Picture`
5. Select the saved image from the image list
6. Click on the image to assign image coordinates for the active point
7. Enter world coordinates for that point
8. Repeat until enough points are filled
9. Click `Extrinsic Calibrate`

### Point Entry Behavior

- Point buttons `P1` to `P5` control the active point
- Clicking the image fills `xi` and `yi` for the active point
- After entering a world point and pressing Enter on the last field, the UI advances to the next point
- `Clear Points` removes the currently displayed image and world point values from the UI and updates the CSV data for that image
- `Delete Image` removes the selected image and its rows from `points.csv`

### Point Prediction

`Calculate_points` uses the first two entered world points to estimate the remaining world points for a checkerboard pattern.

### Tab 2 Requirements

- `points.csv` must contain valid point rows with:
  `image_name`, `points`, `xi`, `yi`, `xw`, `yw`
- Intrinsic calibration files must already exist in `camera_data/`
- At least 4 valid points are required for extrinsic calibration

### Tab 2 Output Files

Saved in `camera_data/`:

- `rvec.npy`
- `tvec.npy`
- `rotation_matrix.npy`
- `Rt_matrix.npy`
- `projection_matrix.npy`

## Mouse Controls In The Image View

In the main UI image display:

- Left click: set a point on the image when point input is active
- Right click drag: pan
- Mouse wheel: zoom

## Standalone Validation Tool

Run:

```bash
python3 calibration_val/main.py
```

Purpose:
Validate saved calibration data by comparing clicked image points with expected world coordinates.

### Validation Steps

1. Select a validation image
2. Select a camera data folder
3. Set the point count
4. Generate rows
5. Fill or load `u`, `v`, `Expected X`, and `Expected Y`
6. Click `Validate`
7. Review predicted coordinates and errors
8. Export CSV if needed

### Validation Camera Files

The selected camera folder must contain:

- `camera_matrix.npy`
- `distortion_coeff.npy`
- `rotation_matrix.npy`
- `tvec.npy`

## Troubleshooting

### No camera detected

- Confirm the camera is connected
- Confirm OpenCV can access the device
- On Linux, make sure camera devices are available under `/dev/video*`

### Qt platform plugin error on Ubuntu

Follow the Ubuntu setup steps in `README.md`, including:

- installing the listed system packages
- removing OpenCV's bundled Qt plugin folder if needed
- setting `QT_QPA_PLATFORM_PLUGIN_PATH`

### Intrinsic calibration fails

- Verify the checkerboard size matches the real board
- Capture sharper images with the full checkerboard visible
- Use at least 3 valid images

### Extrinsic calibration fails

- Confirm `camera_data/` already contains intrinsic calibration files
- Confirm `points.csv` has at least 4 complete rows with `xi`, `yi`, `xw`, and `yw`
- Check that world coordinates are entered in the intended unit system

## Files You Will Use Most Often

- `README.md`: installation and startup
- `USAGE_GUIDE.md`: operating instructions
- `points.csv`: saved extrinsic point correspondences
- `camera_data/`: saved calibration outputs
