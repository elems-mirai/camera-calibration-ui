# Quick Start: Camera Folder Structure

Use one folder for each camera. The app can calibrate from saved images, so the camera does not need to be connected to the UI if you already captured the images another way.

## Recommended Structure

```text
calibration_data/
  usb_camera/
    intrinsic_images/
    extrinsic_images/
    camera_data/
    points.csv

  ip_camera/
    intrinsic_images/
    extrinsic_images/
    camera_data/
    points.csv

  femto_bolt/
    intrinsic_images/
    extrinsic_images/
    camera_data/
    points.csv
```

## What Each Folder Means

- `intrinsic_images/`: checkerboard images for intrinsic calibration.
- `extrinsic_images/`: images used for clicking image points and entering world coordinates.
- `camera_data/`: calibration output files saved by the app.
- `points.csv`: image/world point data used for extrinsic calibration.

## Simple Workflow

1. Create one folder for each camera.
2. Capture checkerboard images outside the UI.
3. Put intrinsic checkerboard images into that camera's `intrinsic_images/` folder.
4. Open the app and select that camera folder.
5. Run intrinsic calibration first.
6. Put extrinsic calibration images into that camera's `extrinsic_images/` folder.
7. In Tab 2, select the same camera folder.
8. Click image points, enter world coordinates, then run extrinsic calibration.

## Example

For an IP camera:

```text
ip_camera/
  intrinsic_images/
    ip_001.jpg
    ip_002.jpg
    ip_003.jpg
  extrinsic_images/
    ip_pose_001.jpg
  camera_data/
  points.csv
```

For a Femto Bolt camera:

```text
femto_bolt/
  intrinsic_images/
    femto_001.png
    femto_002.png
    femto_003.png
  extrinsic_images/
    femto_pose_001.png
  camera_data/
  points.csv
```

## Important Notes

- Keep each camera separate. Do not mix images from different cameras in one folder.
- Use the same image resolution for calibration images from one camera.
- Run intrinsic calibration before extrinsic calibration.
- The current intrinsic square size in the code is `0.022` meters, meaning 22 mm checkerboard squares.
