# Calibration Validation Tool

Phase 2 standalone PyQt5 app for validating image points against expected world points using the same math as `img2world.py`.

## Run

From the repository root:

```bash
python3 calibration_val/main.py
```

## Phase 2 Features

- select validation image
- select camera data folder
- enter point count
- generate point rows
- load point rows from CSV
- select a table row and click the image to fill or replace `u`, `v`
- manually enter `Expected X`, `Expected Y`
- press `Validate`
- view predicted world coordinates, errors, and quality
- export CSV as `points, xi, yi, xw, yw, x_error, y_error, error_norm, quality`

## Quality Bands

Quality is based on `Error Norm` in the same unit as the entered world coordinates:

- `Excellent`: `< 1`
- `Good`: `< 3`
- `Medium`: `< 5`
- `Poor`: `>= 5`

## Required Camera Files

The selected camera folder must contain:

- `new_camera_matrix.npy`
- `rotation_matrix.npy`
- `tvec.npy`

## Click Logic

- choose the row you want to edit
- click the image preview
- that click is converted back to original image pixels
- the selected row receives the new `u`, `v`
- if the click was wrong, keep the same row selected and click again

The newest click replaces the previous point for that row.

## CSV Load

Supported input headers include your format:

- `points`
- `xi`
- `yi`
- `xw`
- `yw`

The loader also accepts common alternatives like `u`, `v`, `expected_x`, `expected_y`.

## Preview Controls

- `Mouse wheel`: zoom in and out around the cursor position
- `Mouse button 3` or middle mouse drag: pan the zoomed image
- `Left click`: assign the current row point
