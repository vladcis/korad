#!/bin/sh
# Self-contained AppImage with a native window (pywebview + Qt WebEngine, everything bundled).
#   pip install -r requirements.txt pyinstaller pywebview qtpy PyQt6 PyQt6-WebEngine
#   sh packaging/linux/build_appimage.sh      -> dist/korad-linux-x86_64.AppImage
# Build on the oldest system you target (glibc); the result runs on newer ones.
set -eu
cd "$(dirname "$0")/../.."
ARCH="${ARCH:-x86_64}"
OUT="dist/korad-linux-$ARCH.AppImage"
APPDIR=build/korad.AppDir

python3 build.py --onedir                      # -> dist/korad/
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib"
cp -a dist/korad "$APPDIR/usr/lib/korad"
# libraries every desktop has and that must match the host's Mesa/X server (AppImage excludelist);
# bundled copies from the old build system break GLX on newer distros (e.g. Debian 13)
( cd "$APPDIR/usr/lib/korad/_internal" && rm -f \
    libX11.so.* libX11-xcb.so.* libXau.so.* libXdmcp.so.* libXext.so.* libXfixes.so.* libXrender.so.* \
    libXdamage.so.* libXcomposite.so.* libXrandr.so.* libXtst.so.* \
    libxcb.so.* libxcb-glx.so.* libxcb-dri2.so.* libxcb-dri3.so.* libxcb-present.so.* libxcb-sync.so.* \
    libxcb-xfixes.so.* libxcb-shm.so.* libxcb-render.so.* libxshmfence.so.* \
    libGL.so.* libGLX.so.* libGLdispatch.so.* libEGL.so.* libgbm.so.* libdrm.so.* libglapi.so.* \
    libwayland-*.so.* libexpat.so.* libfontconfig.so.* libfreetype.so.* libz.so.* libasound.so.* \
    libdbus-1.so.* libgcc_s.so.* libstdc++.so.* \
    libglib-2.0.so.* libgthread-2.0.so.* libgobject-2.0.so.* libgio-2.0.so.* libgmodule-2.0.so.* )
cp packaging/linux/korad.desktop packaging/linux/korad.svg "$APPDIR/"
ln -s korad.svg "$APPDIR/.DirIcon"
cat > "$APPDIR/AppRun" <<'SH'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PYWEBVIEW_GUI="${PYWEBVIEW_GUI:-qt}"
# Chromium sandbox fails inside an AppImage (Ubuntu 24.04+ restricts user namespaces); the window only shows the local UI
export QTWEBENGINE_DISABLE_SANDBOX=1
exec "$HERE/usr/lib/korad/korad" "$@"
SH
chmod 755 "$APPDIR/AppRun"

TOOL="$(command -v appimagetool || true)"
if [ -z "$TOOL" ]; then
  TOOL=build/appimagetool-$ARCH.AppImage
  [ -x "$TOOL" ] || { curl -fsSL -o "$TOOL" \
      "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"; chmod +x "$TOOL"; }
fi
rm -f "$OUT"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo "$OUT"
