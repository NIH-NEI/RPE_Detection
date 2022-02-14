
Packaging into single executable.

1. Download and install Miniconda (or Anaconda).
2. Run Anaconda Prompt, cd to directory '<...>/RPE_Detection'.
3. Create virtual environment (do this once, next time skip to the next step):
   conda env create --file conda-environment-win.yml (Windows 64)
   conda env create --file conda-environment-mac.yml (Mac OS)
4. Activate virtual environment:
   conda activate RPE_Detection
5. (optional step) Make sure the VE is good for running Python code directly:
   python __main__.py
6. Build the target executable:
   make_exe.bat
The resulting exe is: <...>/RPE_Detection/dist/RPE_Detection.exe

Building DMG for Mac:
   sh make_dmg.sh
The resulting DMG disk image is: <...>/RPE_Detection/dist/RPE_Detection.dmg

To delete the virtual environment, deactivate it first (if it is active):
   conda deactivate
Then type:
   conda env remove --name RPE_Detection
