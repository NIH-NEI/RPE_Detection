pyinstaller --clean build-app-dir.spec
rm -rf dist/RPE_Detection/
hdiutil create "RPE_Detection-Darwin.dmg" -ov -volname "RPE_Detection" -fs HFS+ -srcfolder "dist/"
