#!/bin/sh
# .deb package: sources + vendored flask/pywebview, native window via the system WebKitGTK.
# Architecture: all - the same package works on amd64, arm64 (Raspberry Pi)...
#   sh packaging/linux/build_deb.sh 1.1.0      -> dist/korad_1.1.0_all.deb
# Needs: python3-pip, dpkg-deb
set -eu
cd "$(dirname "$0")/../.."
VERSION="${1:-0.0.0}"
VERSION="${VERSION#v}"
ROOT=build/deb/korad
LIB=$ROOT/usr/lib/korad
rm -rf build/deb
mkdir -p "$LIB/static" "$LIB/scripts" "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/lib/udev/rules.d" "$ROOT/usr/share/doc/korad" dist

cp app.py korad.py scripting.py sequencer.py datalog.py desktop.py "$LIB/"
cp static/* "$LIB/static/"
cp scripts/*.py "$LIB/scripts/"
# pure-Python deps (Ubuntu 22.04 / Debian 12 ship no Flask 3); markupsafe and pyserial come from the system
python3 -m pip install --quiet --no-compile --target "$LIB/vendor" "flask>=3.0" "pywebview>=5.0"
rm -rf "$LIB/vendor/bin" "$LIB/vendor"/markupsafe "$LIB/vendor"/[Mm]arkup[Ss]afe-*
cp packaging/linux/korad.desktop "$ROOT/usr/share/applications/"
cp packaging/linux/korad.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/"
# uaccess (before 73-seat-late) = the logged-in user gets access to the PSU even without the dialout group
sed 's/SYMLINK+="korad"/SYMLINK+="korad", TAG+="uaccess"/' 99-korad.rules > "$ROOT/usr/lib/udev/rules.d/70-korad.rules"
cp README.md "$ROOT/usr/share/doc/korad/"

cat > "$ROOT/usr/bin/korad" <<'SH'
#!/bin/sh
export KORAD_HOME="${KORAD_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/korad}"
export PYTHONPATH="/usr/lib/korad/vendor${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
exec python3 /usr/lib/korad/desktop.py "$@"
SH
chmod 755 "$ROOT/usr/bin/korad"

for s in postinst postrm; do
  cat > "$ROOT/DEBIAN/$s" <<'SH'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules 2>/dev/null || true
  udevadm trigger --subsystem-match=tty 2>/dev/null || true
fi
SH
  chmod 755 "$ROOT/DEBIAN/$s"
done

cat > "$ROOT/DEBIAN/control" <<CTL
Package: korad
Version: $VERSION
Architecture: all
Maintainer: vladcis <vladcis@users.noreply.github.com>
Section: electronics
Priority: optional
Installed-Size: $(du -sk "$ROOT" | cut -f1)
Depends: python3 (>= 3.10), python3-serial, python3-markupsafe, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Homepage: https://github.com/vladcis/korad
Description: control app for KORAD KA3005P/PS lab power supply
 GUI for KORAD KA3005P / KA3005PS (and clones: Tenma 72-2535, RND 320-KA3005P,
 Velleman LABPS3005D) connected over USB: front-panel view, live chart,
 programmable sequences, Python scripting (battery charging) and CSV logging.
CTL

find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT" -type f ! -perm -u+x -exec chmod 644 {} +
OUT="dist/korad_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT"
echo "$OUT"
