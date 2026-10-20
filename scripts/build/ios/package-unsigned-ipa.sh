#!/usr/bin/env bash
# Assemble an ad-hoc signed, engine-only IPA for sideloading.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
APP_NAME=GeneralsXZH
APP="$ROOT/build/ios-package/Payload/$APP_NAME.app"
BIN="$ROOT/build/ios-vulkan/GeneralsMD/GeneralsXZH.app/$APP_NAME"
DXVK="$ROOT/build/ios-vulkan/_deps/dxvk-build-macos"
DEPS="$ROOT/build/ios-vulkan/_deps"
OUT="$ROOT/build/ios-package"
: "${GX_BUNDLE_ID:=com.roundedspine.generalszh}"
test -f "$BIN" || { echo "Missing engine executable: $BIN"; exit 1; }
rm -rf "$OUT"
mkdir -p "$APP/Frameworks" "$APP/GameData/fonts"
cp "$BIN" "$APP/$APP_NAME"
cp ios/config/dxvk.conf "$APP/GameData/dxvk.conf"
cp ios/config/Options.ini "$APP/GameData/DefaultOptions.ini"
: "${GX_FONTS:=$HOME/GeneralsX/ios-staging/fonts}"
cp "$GX_FONTS"/*.ttf "$APP/GameData/fonts/"
python3 - "$APP/Info.plist" "$GX_BUNDLE_ID" <<'PY'
import plistlib,sys
path,bundle=sys.argv[1:]
info=dict(CFBundleIdentifier=bundle,CFBundleExecutable="GeneralsXZH",
 CFBundleName="GeneralsXZH",CFBundleDisplayName="Generals ZH",
 CFBundlePackageType="APPL",CFBundleShortVersionString="1.04",
 CFBundleVersion="1",MinimumOSVersion="16.0",
 UIDeviceFamily=[1,2],UIFileSharingEnabled=True,
 LSSupportsOpeningDocumentsInPlace=True,UIRequiresFullScreen=True,
 UIStatusBarHidden=True,UIApplicationSupportsIndirectInputEvents=True,
 UISupportedInterfaceOrientations=["UIInterfaceOrientationLandscapeLeft","UIInterfaceOrientationLandscapeRight"])
with open(path,"wb") as f: plistlib.dump(info,f)
PY
for lib in \
 "$DXVK/src/d3d8/libdxvk_d3d8.0.dylib" \
 "$DXVK/src/d3d9/libdxvk_d3d9.0.dylib" \
 "$DEPS/sdl3-build/libSDL3.0.dylib" \
 "$DEPS/sdl3_image-build/libSDL3_image.0.dylib" \
 "$DEPS/openal_soft-build/libopenal.1.24.2.dylib"; do
 test -f "$lib" || { echo "Missing runtime: $lib"; exit 1; }
 cp "$lib" "$APP/Frameworks/"
done
mv "$APP/Frameworks/libopenal.1.24.2.dylib" "$APP/Frameworks/libopenal.1.dylib"
if test -f "$ROOT/build/ios-vulkan/libgamespy.dylib"; then cp "$ROOT/build/ios-vulkan/libgamespy.dylib" "$APP/Frameworks/"; fi
: "${GX_MOLTENVK:=$HOME/GeneralsX/MoltenVK/MoltenVK/MoltenVK/dynamic/MoltenVK.xcframework/ios-arm64/MoltenVK.framework}"
test -d "$GX_MOLTENVK" || { echo "Missing MoltenVK: $GX_MOLTENVK"; exit 1; }
cp -R "$GX_MOLTENVK" "$APP/Frameworks/"
install_name_tool -add_rpath "@executable_path/Frameworks" "$APP/$APP_NAME" 2>/dev/null || true
find "$APP/Frameworks" -name '*.dylib' -type f -exec codesign --force --sign - --timestamp=none {} \;
codesign --force --sign - --timestamp=none "$APP/Frameworks/MoltenVK.framework"
codesign --force --sign - --timestamp=none "$APP"
codesign --verify --deep "$APP"
(cd "$OUT" && zip -qry "GeneralsZH-engine-only-unsigned.ipa" Payload)
echo "IPA: $OUT/GeneralsZH-engine-only-unsigned.ipa"
