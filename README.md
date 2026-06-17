# Camera_calibration_UI

## Documentation

- See `USAGE_GUIDE.md` for the full operating guide for Tab 1, Tab 2, folder layout, outputs, and the validation tool.

# Ubuntu Installation Guide
``` 
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```
```
sudo apt update
sudo apt install -y libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor0 libx11-xcb1 libglu1-mesa
```
```
rm -rf .venv/lib/python3.10/site-packages/cv2/qt
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms
```

## Run  UI

```
python3 main.py
```
# Windows Installation Guide
1. Download and install Python [click here](https://www.python.org/downloads/release/python-3120/)

    !! During Python installation, select the option “Add Python to PATH.

2. Download and install Git bash [click here](https://git-scm.com/install/windows)

3.  open gitbash in project folder 
    - clik mouse right button and click "Show more options"
    - Click "Open Git Bash here"
4.  run those commands in gitbash terminal

```
# create virtual environment
python -m venv .venv
select virtual environment
source .venv/Scripts/activate
# install libraries
pip install -r requirements.txt
```

Run ui 
```
python main.py
```
