#!/bin/bash
set -e

ARCH="amd64"
PKG_NAME="simeismma"
BUILD_DIR="packaging/debian-build"

rm -rf "$BUILD_DIR"
mkdir -p \
  "$BUILD_DIR/DEBIAN" \
  "$BUILD_DIR/usr/bin" \
  "$BUILD_DIR/usr/share/man/man1" \
  "$BUILD_DIR/etc/systemd/system"

cp target/release/simeis-server "$BUILD_DIR/usr/bin/simeismma"
cp packaging/simeismma.1.gz "$BUILD_DIR/usr/share/man/man1/"
cp packaging/simeismma.service "$BUILD_DIR/etc/systemd/system/"
cp packaging/control "$BUILD_DIR/DEBIAN/control"

dpkg-deb --build "$BUILD_DIR" "${PKG_NAME}_${ARCH}.deb"