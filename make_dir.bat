pyinstaller --clean --noconfirm build-dir.spec
PowerShell -Command Compress-Archive -Path dist\RPE_Detection\* -DestinationPath dist\RPE_Detection-1.2.1-win64.zip -Force
