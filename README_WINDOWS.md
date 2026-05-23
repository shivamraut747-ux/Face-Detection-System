# Windows Setup

This project was cleaned up for Windows use.

## What changed

- Database access now uses the project folder instead of the current terminal folder.
- A Windows setup script and launcher were added.
- The app now shows a clear setup message if face-recognition dependencies are missing.
- macOS archive leftovers can be ignored.

## Recommended Python

Use Python 3.11 (64-bit).

Python 3.13 and 3.14 are a bad fit for this project on Windows because `dlib` and `face_recognition` commonly fail to build there.

The setup script also keeps `setuptools` on a compatible version because `face_recognition_models` still depends on `pkg_resources`.

## First-time setup

Open PowerShell in this folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

## Start the app

```powershell
.\run_windows.bat
```

## Camera permissions

If the live scanner or registration camera does not open:

- Allow camera access for your browser in Windows Settings.
- Allow camera access for the browser tab that Streamlit opens.
- If needed, close other apps that are already using the webcam.

## Project folder

Work from this folder:

`C:\Users\shiva\Documents\Codex\2026-04-18-files-mentioned-by-the-user-mini\mini-project\mini-project`
