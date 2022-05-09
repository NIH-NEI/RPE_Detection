rm -rf build/
rm -rf dist/
pyinstaller --clean --noconfirm build-app-dir.spec
rm -rf dist/RPE_Detection/
hdiutil create "dist/RPE_Detection-Darwin0.dmg" -format UDRW -ov -volname "RPE_Detection" -fs HFS+ -srcfolder "dist/" -attach
ln -s /Applications /Volumes/RPE_Detection/Applications
mkdir /Volumes/RPE_Detection/.background
cp MacOS/DMGbackground.tif /Volumes/RPE_Detection/.background/background.tif
osascript MacOS/DMGSetup.scpt RPE_Detection
hdiutil detach /Volumes/RPE_Detection
python MacOS/licenseDMG.py dist/RPE_Detection-Darwin0.dmg Help/License.txt
rm dist/RPE_Detection-1.1.0-Darwin.dmg
hdiutil convert dist/RPE_Detection-Darwin0.dmg -format UDZO -o dist/RPE_Detection-1.1.2-Darwin.dmg
rm dist/RPE_Detection-Darwin0.dmg
