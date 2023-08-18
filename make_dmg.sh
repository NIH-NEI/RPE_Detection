APPNAME="RPE_Detection"
VERSION="1.1.3"
rm -rf build/
rm -rf dist/
pyinstaller --clean --noconfirm build-app-dir.spec
rm -rf "dist/${APPNAME}/"
cd "dist/${APPNAME}.app/Contents/MacOS"
mv PyQt5/ ../Resources/
ln -s ../Resources/PyQt5 .
cd ../Resources/
ln -s ../MacOS/Qt* .
cd ../../../..
codesign --force --deep --verbose -s - "dist/${APPNAME}.app"
codesign --verify --verbose --strict "dist/${APPNAME}.app"
hdiutil create "${APPNAME}-Darwin0.dmg" -format UDRW -ov -volname "${APPNAME}" -fs HFS+ -srcfolder "dist/" -attach
ln -s /Applications "/Volumes/${APPNAME}/Applications"
mkdir "/Volumes/${APPNAME}/.background"
cp MacOS/DMGbackground.tif "/Volumes/${APPNAME}/.background/background.tif"
osascript MacOS/DMGSetup.scpt "${APPNAME}"
hdiutil detach "/Volumes/${APPNAME}"
#python MacOS/licenseDMG.py ${APPNAME}-Darwin0.dmg Help/License.txt
hdiutil convert "${APPNAME}-Darwin0.dmg" -format UDZO -o "dist/${APPNAME}-${VERSION}-Darwin.dmg"
rm "${APPNAME}-Darwin0.dmg"
dmg-license MacOS/dmg-license-spec.json "dist/${APPNAME}-${VERSION}-Darwin.dmg"
