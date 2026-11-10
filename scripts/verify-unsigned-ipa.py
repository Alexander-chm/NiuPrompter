#!/usr/bin/env python3
"""Validate device-only packaging before uploading an unsigned IPA."""
import hashlib
import json
import pathlib
import plistlib
import re
import subprocess
import sys
import zipfile

ipa = pathlib.Path(sys.argv[1])
app = pathlib.Path(sys.argv[2])
with zipfile.ZipFile(ipa) as archive:
    assert archive.testzip() is None, "Corrupt ZIP member"
    names = archive.namelist()
    plists = [name for name in names if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)]
    assert len(plists) == 1, "Expected exactly one top-level application"
    info = plistlib.loads(archive.read(plists[0]))
    assert info["CFBundlePackageType"] == "APPL"
    assert info["MinimumOSVersion"] == "26.0", "Unexpected minimum system version"
    assert set(info["UIDeviceFamily"]) == {1, 2}, "iPhone and iPad must both be supported"
    assert info["CFBundleSupportedPlatforms"] == ["iPhoneOS"], "Simulator build is not installable"
    executable = info["CFBundleExecutable"]
    entry = plists[0].removesuffix("Info.plist") + executable
    assert archive.getinfo(entry).external_attr >> 16 & 0o111, "Executable permission missing"
    assert not any(name.endswith("embedded.mobileprovision") or "/_CodeSignature/" in name for name in names), "Expected unsigned app"
    for key in ("NSCameraUsageDescription", "NSMicrophoneUsageDescription", "NSPhotoLibraryAddUsageDescription"):
        assert info.get(key), f"Missing privacy description: {key}"

binary = app / executable
arch = subprocess.check_output(["xcrun", "lipo", "-archs", str(binary)], text=True).strip()
assert arch == "arm64", f"Unexpected architectures: {arch}"
build = subprocess.check_output(["xcrun", "vtool", "-show-build", str(binary)], text=True)
assert re.search(r"platform\s+IOS\b", build), "Mach-O platform is not iOS device"
assert re.search(r"minos\s+26\.0\b", build), "Mach-O minimum OS differs from Info.plist"
load_commands = subprocess.check_output(["xcrun", "otool", "-l", str(binary)], text=True)
assert not re.search(r"cryptid\s+[1-9]", load_commands), "Encrypted executable cannot be re-signed"
signature = subprocess.run(["codesign", "-dv", str(app)], capture_output=True, text=True)
assert signature.returncode != 0 and "not signed at all" in signature.stderr, "App unexpectedly has a signature"

print(json.dumps({
    "status": "passed",
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "sha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
    "bundle_identifier": info["CFBundleIdentifier"],
    "display_name": info.get("CFBundleDisplayName"),
    "minimum_os": info["MinimumOSVersion"],
    "device_families": info["UIDeviceFamily"],
    "architecture": arch,
    "signed": False,
    "device_installation_tested": False,
    "xcode": subprocess.check_output(["xcodebuild", "-version"], text=True).strip(),
}, ensure_ascii=False, indent=2))
