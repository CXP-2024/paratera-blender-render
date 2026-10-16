#!/bin/bash
# Run ON the instance (Ubuntu 24.04 PyTorch image, driver 550.54.14). Idempotent-ish.
# Installs Blender 4.2 LTS + X/GL runtime libs + NVIDIA userspace GL/EGL/OptiX libs.
# Without the NVIDIA GL libs, EEVEE silently falls back to CPU llvmpipe (~100x slower)
# and OptiX is unavailable (container only ships compute libs).
set -u
BLENDER_SERIES=${BLENDER_SERIES:-4.2}
cd /root

if [ ! -x blender/blender ]; then
  VER=$(curl -s -m 20 https://download.blender.org/release/Blender${BLENDER_SERIES}/ \
        | grep -o "blender-${BLENDER_SERIES}\.[0-9]*-linux-x64.tar.xz\"" | sort -V | tail -1 | tr -d '"')
  echo "Blender tarball: $VER"
  wget -q -O blender.tar.xz https://download.blender.org/release/Blender${BLENDER_SERIES}/$VER
  tar xf blender.tar.xz && rm blender.tar.xz
  mv blender-${BLENDER_SERIES}.*-linux-x64 blender
fi

apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 xvfb >/dev/null 2>&1

# NVIDIA userspace libs must match the host driver version exactly.
V=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "driver $V"
[ -f NVIDIA-$V.run ] || wget -q -O NVIDIA-$V.run https://download.nvidia.com/XFree86/Linux-x86_64/$V/NVIDIA-Linux-x86_64-$V.run
[ -d nvx ] || sh NVIDIA-$V.run -x --target nvx >/dev/null 2>&1
L=/usr/lib/x86_64-linux-gnu
for f in libEGL_nvidia libGLX_nvidia libnvidia-glcore libnvidia-eglcore libnvidia-glsi libnvidia-rtcore libnvoptix libnvidia-tls libnvidia-glvkspirv; do
  [ -f nvx/$f.so.$V ] && cp nvx/$f.so.$V $L/
done
ln -sf $L/libEGL_nvidia.so.$V $L/libEGL_nvidia.so.0
ln -sf $L/libGLX_nvidia.so.$V $L/libGLX_nvidia.so.0
ln -sf $L/libnvoptix.so.$V $L/libnvoptix.so.1
mkdir -p /usr/share/glvnd/egl_vendor.d && cp nvx/10_nvidia.json /usr/share/glvnd/egl_vendor.d/
ldconfig
./blender/blender -b --version | head -1
echo setup-done
