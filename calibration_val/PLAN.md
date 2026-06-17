# Calibration Validation Qt Plan

## Goal
Build a Qt-based validation application inside `calibration_val/` for checking image points against world points.

The user workflow will be:
1. Open the validation app.
2. Choose image and camera calibration data.
3. Enter how many points will be validated.
4. Enter or load the expected world points.
5. Click or enter image points.
6. Press `Validate`.
7. Run the same image-to-world calculation logic as `img2world.py`.
8. Show predicted world coordinates and error for each point.
9. Save the validation result to CSV.

## Current Repo Facts
- `img2world.py` already contains the core projection math:
  - load `new_camera_matrix.npy`
  - load `rotation_matrix.npy`
  - load `tvec.npy`
  - convert image `(u, v)` to world `(x, y, z=0)`
- `validate_two_image_points.py` already contains reusable logic for:
  - camera model loading
  - image-to-world prediction
  - error calculation
  - summary CSV output
- The main project already uses `PyQt5`, so the new validator should also use `PyQt5` for consistency.

## Proposed Scope
Create a standalone Qt validation tool under `calibration_val/` instead of mixing it into the existing calibration tabs first.

The first version should include:
- point count input
- image file selection
- camera data folder selection
- optional world point CSV load
- manual table for point rows
- image preview with point clicking
- `Validate` button
- result table with predicted coordinates and error
- CSV export

The first version should not include:
- live camera capture
- multi-image batch validation
- advanced plotting
- packaging installer

## Planned Structure
Suggested files in `calibration_val/`:

- `main.py`
  Qt application entry point.
- `window.py`
  Main validator window and widget wiring.
- `validator.py`
  Validation service that runs the `img2world.py` equivalent math.
- `image_canvas.py`
  Qt image widget for showing the image and collecting clicked points.
- `models.py`
  Dataclasses for point rows and validation results.
- `io_utils.py`
  File loading and CSV saving helpers.
- `README.md`
  Usage instructions for the validation tool.

## UI Plan
Main window layout:

- Left panel
  - image selector
  - camera data selector
  - point count input
  - world point CSV loader
  - `Add Rows` button
  - `Validate` button
  - `Export CSV` button

- Center panel
  - image preview
  - click-to-pick point support
  - current selected row indicator

- Right or bottom panel
  - editable table with one row per point
  - columns:
    - point id
    - image u
    - image v
    - expected x
    - expected y
    - predicted x
    - predicted y
    - error x
    - error y
    - error norm
    - status

## Validation Logic Plan
The validator logic will directly match `img2world.py` behavior:

1. Load:
   - `new_camera_matrix.npy`
   - `rotation_matrix.npy`
   - `tvec.npy`
2. Compute inverse camera matrix and inverse rotation matrix.
3. For each image point `(u, v)`:
   - deproject with scale `0`
   - deproject with scale `1`
   - intersect the ray with world plane `z = 0`
4. Compare predicted `(x, y)` with expected `(x, y)`.
5. Store:
   - predicted world point
   - error in x
   - error in y
   - Euclidean error norm

## Implementation Steps
1. Create the `calibration_val/` Qt app skeleton and file layout.
2. Extract the `img2world.py` math into a reusable validator module.
3. Build the main Qt window and forms for file selection and point count.
4. Implement the image viewer with point-click support.
5. Implement the point table and row selection behavior.
6. Connect the `Validate` button to the validator logic.
7. Show computed results and validation errors in the UI.
8. Add CSV import/export for point lists and validation summaries.
9. Write `README.md` with run instructions and expected folder/file format.
10. Test against the existing sample camera data in this repository.

## Input/Output Plan
Inputs:
- image file (`.jpg`, `.png`, ...)
- camera data directory
- number of points
- expected world points from table or CSV
- image points from clicks or manual entry

Outputs:
- on-screen validation table
- CSV report with all point results

Suggested CSV output columns:
- `point_id`
- `image_name`
- `camera_dir`
- `u`
- `v`
- `expected_x`
- `expected_y`
- `predicted_x`
- `predicted_y`
- `error_x`
- `error_y`
- `error_norm`

## Risks To Handle
- wrong camera folder chosen by user
- missing `.npy` files
- point count not matching loaded CSV rows
- invalid numeric input
- clicking scaled image but storing original pixel coordinates
- inconsistent coordinate units between world points and calibration data

## Acceptance Criteria
- The app runs from `calibration_val/`.
- The user can enter the number of points.
- The user can select an image and camera data folder.
- The user can fill or load expected world points.
- The user can assign image points by clicking.
- Pressing `Validate` runs the same conversion logic as `img2world.py`.
- The app shows predicted coordinates and errors for every point.
- The app can export the results to CSV.

## Delivery Order
Phase 1:
- working Qt window
- point count input
- image load
- camera data load
- validate button wired to math

Phase 2:
- clickable image mapping
- editable point table
- CSV import/export

Phase 3:
- polish
- error messages
- usage documentation
