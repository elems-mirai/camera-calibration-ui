import cv2
import numpy as np
import matplotlib.pyplot as plt

# Your inner corners
CORNERS_X = 10
CORNERS_Y = 4

cap = cv2.VideoCapture(4)
if not cap.isOpened():
    raise RuntimeError("Cannot open camera")

plt.ion()  # interactive mode
fig, ax = plt.subplots()

img_plot = None

while True:
    ok, frame = cap.read()
    if not ok:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    found, corners = cv2.findChessboardCorners(gray, (CORNERS_X, CORNERS_Y), None)

    if found:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        cv2.drawChessboardCorners(frame, (CORNERS_X, CORNERS_Y), corners, found)
        text = f"Found {len(corners)} corners"
        color = (0, 255, 0)
    else:
        text = "No chessboard found"
        color = (255, 0, 0)

    # Convert BGR → RGB for matplotlib
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    if img_plot is None:
        img_plot = ax.imshow(frame_rgb)
        ax.axis('off')
    else:
        img_plot.set_data(frame_rgb)

    ax.set_title(text)

    plt.pause(0.001)

    # press Ctrl+C in terminal to stop

cap.release()
plt.ioff()
plt.close()