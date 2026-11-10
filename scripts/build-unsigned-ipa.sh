#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
command -v xcodegen >/dev/null
command -v xcodebuild >/dev/null
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/niuprompter-unsigned.XXXXXX")"
mkdir -p dist

# The generated project and all build products stay outside version control.
bash scripts/generate-ios-project.sh
xcodebuild \
  -project SmartTeleprompterProbe-iPadProject.xcodeproj \
  -scheme SmartTeleprompterProbe-iPad \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$BUILD_ROOT/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY= \
  DEVELOPMENT_TEAM= \
  ARCHS=arm64 \
  ONLY_ACTIVE_ARCH=NO \
  build

APP="$BUILD_ROOT/DerivedData/Build/Products/Release-iphoneos/SmartTeleprompterProbe-iPad.app"
test -d "$APP"
mkdir -p "$BUILD_ROOT/staging/Payload"
ditto "$APP" "$BUILD_ROOT/staging/Payload/$(basename "$APP")"
(
  cd "$BUILD_ROOT/staging"
  COPYFILE_DISABLE=1 /usr/bin/zip -qry "$BUILD_ROOT/NiuPrompter-unsigned.ipa" Payload
)
python3 scripts/verify-unsigned-ipa.py \
  "$BUILD_ROOT/NiuPrompter-unsigned.ipa" "$APP" > dist/verification.json
cp "$BUILD_ROOT/NiuPrompter-unsigned.ipa" dist/NiuPrompter-unsigned.ipa
(
  cd dist
  shasum -a 256 NiuPrompter-unsigned.ipa > NiuPrompter-unsigned.ipa.sha256
)
cat dist/verification.json
printf '\nUnsigned IPA ready: %s/dist/NiuPrompter-unsigned.ipa\n' "$PROJECT_ROOT"
