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
site_packages="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
unicorn_package_dir="$site_packages/unicorn"
unicorn_library="$(find "$unicorn_package_dir" -type f -name 'libunicorn.so*' -print -quit 2>/dev/null || true)"

if [ -z "$unicorn_library" ]; then
    echo "[!] Could not find libunicorn.so inside $unicorn_package_dir"
    exit 1
fi

unicorn_lib_dir="$(dirname "$unicorn_library")"
unicorn_library_name="$(basename "$unicorn_library")"
ln -sfn "$unicorn_library_name" "$unicorn_lib_dir/libunicorn.so"
echo "    Linked $unicorn_lib_dir/libunicorn.so -> $unicorn_library_name"

python -c 'import unicorn; print("Unicorn:", unicorn.__version__)'
echo "[OK] Termux installation completed."
