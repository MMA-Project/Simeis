#!/bin/bash
set -e

VERSION="1.0.0"
ARCH="amd64"
PKG_NAME="simeis"
BUILD_DIR="packaging/debian-build"

rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

mkdir -p $BUILD_DIR/DEBIAN
mkdir -p $BUILD_DIR/usr/bin
mkdir -p $BUILD_DIR/usr/share/man/man1
mkdir -p $BUILD_DIR/etc/systemd/system

cp target/release/simeis-server $BUILD_DIR/usr/bin/
cp packaging/simeis.1.gz $BUILD_DIR/usr/share/man/man1/
cp packaging/simeis.service $BUILD_DIR/etc/systemd/system/

fakeroot dpkg-deb --build $BUILD_DIR ${PKG_NAME}_${VERSION}_${ARCH}.deb
