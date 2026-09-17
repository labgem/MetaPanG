#!/usr/bin/env bash
set -e

micromamba create -p ./appdir/usr/env -y -f ./env.yaml
micromamba activate ./appdir/usr/env
pip install ../..
micromamba deactivate

wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

./appimagetool-x86_64.AppImage ./appdir
rm appimagetool-x86_64.AppImage