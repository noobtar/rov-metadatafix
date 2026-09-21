#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
    echo "[!] This installer must be run inside Termux."
    exit 1
fi

echo "[1/5] Updating Termux packages..."
pkg update
pkg upgrade -y

echo "[2/5] Installing build tools..."
pkg install python cmake clang make -y

echo "[3/5] Updating Python build tools..."
python -m pip install --upgrade pip setuptools wheel

echo "[4/5] Building Unicorn 2.1.4 from source..."
python -m pip install --no-cache-dir --no-binary unicorn unicorn==2.1.4

echo "[5/5] Creating the Unicorn shared-library link..."
unicorn_lib_dir="$(python -c 'import pathlib, unicorn; print(pathlib.Path(unicorn.__file__).parent / "lib")')"
if [ ! -f "$unicorn_lib_dir/libunicorn.so.2" ]; then
    echo "[!] Could not find $unicorn_lib_dir/libunicorn.so.2"
    exit 1
fi
ln -sf libunicorn.so.2 "$unicorn_lib_dir/libunicorn.so"

python -c 'import unicorn; print("Unicorn:", unicorn.__version__)'
echo "[OK] Termux installation completed."
