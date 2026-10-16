#!/bin/bash
# Run ON the instance. Installs Node 20 (official tarball) + yarn, and unpacks VMDPhysicsBake
# from /root/vpb_slim.tgz (upload it first: GitHub is very slow/unreliable from the instance and the
# SSH gateway uploads at only ~13 KB/s, so ship a slim tarball: no .git, no demo/assets/dafeng).
# Make the tarball locally:
#   git clone --depth 1 git@github.com:yyc-git/VMDPhysicsBake.git vpb
#   tar czf vpb_slim.tgz --exclude=.git --exclude=demo/assets/dafeng --exclude=node_modules vpb
set -e
cd /root
if [ ! -x /opt/node/bin/node ]; then
  V=$(curl -s -m 20 https://nodejs.org/dist/latest-v20.x/ | grep -o 'node-v20\.[0-9.]*-linux-x64.tar.xz' | head -1)
  wget -q -O node.tar.xz https://nodejs.org/dist/latest-v20.x/$V
  mkdir -p /opt/node && tar xf node.tar.xz -C /opt/node --strip-components=1 && rm node.tar.xz
fi
for b in node npm npx; do ln -sf /opt/node/bin/$b /usr/local/bin/$b; done
/opt/node/bin/npm install -g yarn >/dev/null 2>&1; ln -sf /opt/node/bin/yarn /usr/local/bin/yarn
mkdir -p /root/tools && cd /root/tools
if [ -f /root/vpb_slim.tgz ]; then
  rm -rf VMDPhysicsBake vpb
  tar xzf /root/vpb_slim.tgz --no-same-owner && mv vpb VMDPhysicsBake && rm /root/vpb_slim.tgz
fi
cd VMDPhysicsBake && yarn install --frozen-lockfile 2>&1 | tail -2
yarn bake 2>&1 | tail -2    # self-test: 90 frames in ~6 s, headless, no GPU needed
echo tools-done
