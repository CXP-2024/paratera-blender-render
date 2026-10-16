---
name: paratera-blender-render
description: Rent a GPU container on Paratera (并行科技 / 智算云, ai.blsc.cn, ai.paratera.com), install headless Blender with working GPU EEVEE/Cycles, render over SSH, and stop the instance to stop billing. Use when the user wants to render Blender / MMD animations on a remote Paratera GPU server, compare GPU cost, or manage that platform's instances through its Python SDK.
---

# Remote Blender rendering on Paratera container cloud

Everything here was verified on a real RTX 3090 instance (Ubuntu 24.04 PyTorch image, driver 550.54.14,
Blender 4.2 LTS). Scripts are in `scripts/`; run them with the user's Python.

## Hard rules
- **Creating an instance bills money.** Never create one unless the user asked for it in this conversation.
  `para.py create` is a dry run (prints the price) unless `--yes` is passed.
- **Always stop when done**, and confirm the status is `Stopped`. Stopping inside the OS does NOT stop billing;
  use `para.py stop` (or the console). Stopping with `saveEnv=false` wipes the system disk (Blender install is lost).
- Never print or commit AK/SK or the instance password. Credentials are read from files; the SSH password is
  cached in `~/.paratera/ssh_<uuid>.json`.
- Arrears -> instances are deleted unrecoverably. Keep important data on shared storage, not the 30 GB system disk.

## One-time setup
1. Python 3 + `pip install paramiko requests`.
2. The platform SDK is **not on PyPI**: the user downloads `aicloud_sdk_python-3.0-py3-none-any.whl` from the
   platform docs (API docs -> SDK) and you `pip install` it. Then run `python scripts/patch_sdk.py`
   (the wheel imports the non-existent `_sha256` on Python >= 3.12). The wheel installs top-level packages named
   `client`, `common`, `ecs`, ... into site-packages; prefer a dedicated venv.
3. Credentials: AccessKey / SecretKey from the platform's personal center (个人中心), saved as two files,
   default `~/.ssh/para_ak` and `~/.ssh/para_sk` (override with `PARA_AK_FILE`, `PARA_SK_FILE`).
   They are **API keys, not SSH keys**. API host is `ai.blsc.cn` (the SDK default).
4. Smoke test (read-only, free): `python scripts/para.py types` -> prices for all 1-GPU models.

## Workflow
```bash
python scripts/para.py types                                   # models, zones, live CNY/h
python scripts/para.py create --zone cn-zhongwei-ac --model rtx3090.epyc7402.xlarge            # dry run + price
python scripts/para.py create --zone cn-zhongwei-ac --model rtx3090.epyc7402.xlarge --yes       # BILLS; waits for Running, caches SSH login
python scripts/remote.py UUID put scripts/setup_instance.sh /root/setup_instance.sh
python scripts/remote.py UUID run "bash /root/setup_instance.sh" 900     # Blender + NVIDIA GL/OptiX libs (~5 min)
python scripts/remote.py UUID put my_scene.blend /root/my_scene.blend
python scripts/remote.py UUID run "cd /root && ./blender/blender -b my_scene.blend -a" 3600
python scripts/remote.py UUID get /root/out/f_0001.png ./f_0001.png
python scripts/para.py stop --zone cn-zhongwei-ac --uuid UUID           # always
```
SSH login is `root@<uuid>` on `ssh.zw1.paratera.com:2222` with a password from `DescribeServicesSSH`.
Server-side `scp`/`rsync` through that gateway also works; `remote.py put/get` uses SFTP.

## Prebuilt image (fastest start)
Image **`ackci-00gjhvds`** ("blender-mmd-3090", zone `cn-zhongwei-ac`, GPU type rtx3090 only) already contains
Blender 4.2.23 at `/root/blender`, the NVIDIA GL/EGL/OptiX libs (GPU EEVEE works), Node 20 + yarn, and
VMDPhysicsBake at `/root/tools/VMDPhysicsBake`. Boot from it and skip all setup (verified: `yarn bake` OK,
EEVEE 30 frames in 17 s):
```bash
python scripts/para.py create --zone cn-zhongwei-ac --model rtx3090.epyc7402.xlarge --image ackci-00gjhvds --yes
```
Images are per zone and per GPU type; a 4090/5090 needs its own image built the same way. If the image is gone
(or for another GPU), build one: create from the stock image -> `setup_instance.sh` -> `setup_tools.sh` ->
`para.py stop --save-env` -> wait until `Stopped` -> `para.py image --name ...` (takes ~1 min; it is billed
CNY 0.00048/GB/h). **The API only accepts images from a Stopped instance** (the docs wrongly say Running), and
stopping with `saveEnv=false` wipes the disk, so you must stop with `--save-env` first.
Shared storage is mounted at `/root/shared-nvme` (JuiceFS, 50 GB free, survives stop/delete); `/shared-public` is
a read-only public mount. Put `.blend`/PMX/VMD assets there to avoid re-uploading.

## MMD pipeline: VMDPhysicsBake (github.com/yyc-git/VMDPhysicsBake, MIT)
Headless Node tool: PMX + action VMD -> VMD with baked per-frame physics bones (Ammo.js), deterministic,
no GPU/browser needed. On the instance: `cd /root/tools/VMDPhysicsBake`, then
`node src/tool/bake-physics.mjs --pmx <model.pmx> --vmd <motion.vmd> --output output/x_bake.vmd`
(`yarn bake` = bundled demo, ~6 s; `yarn verify` = assertions V1-V6, all PASS on the image). Config knobs are in
`src/tool/bake-config*.json`. Then import the baked VMD into Blender with mmd_tools (not installed yet) and render.

## Prices measured 2026-10 (pay-as-you-go, per hour, 1 GPU, 10-14 CPU cores)
RTX 3090 1.30 (zone cn-zhongwei-ac) - RTX 4090 1.88 (cn-zhongwei-bc, ap-shandong-cd; cn-zhongwei-cc has 14 cores/120 GB) -
RTX 5090 2.98. 2-GPU 3090 is 2.60. Billing is per second, settled hourly (docs); no minimum stated.
Re-check with `para.py types`.

## Gotchas that cost time (all verified)
1. **EEVEE silently runs on CPU** (77 s/frame vs 0.55 s on a 3090) because the container has only NVIDIA compute
   libs. `setup_instance.sh` extracts the userspace GL/EGL/OptiX libs from NVIDIA's installer matching the
   driver version and registers the EGL vendor file. After it, `blender -b` EEVEE uses the GPU with no Xvfb.
2. First EEVEE frame of each Blender process spends ~30 s compiling shaders; render the whole animation in one
   process (`-a`), not one process per frame.
3. Cycles: without the NVIDIA libs OptiX is unavailable and a device list filtered on OPTIX picks nothing -> falls
   back to CPU (GPU util 0%). Use `CYCLES_DEVICE=CUDA` (default in `bench_scene.py`) or OPTIX after setup.
   Check `nvidia-smi` utilisation during a render to be sure.
4. **SDK request classes are broken**: class attributes shadow dict keys, and enums are not JSON serialisable.
   `para_common.call()` sends plain dicts via `GenericRequest`; `billingType` is the string `"PostPaid"`.
5. Zone codes from `DescribeZones` (e.g. `cn-zhongwei-a`) differ from container-cloud zones (`cn-zhongwei-ac`).
   Container zones come from `DescribeACKServiceTypes`. Always list 1-GPU models explicitly: the first page of
   output hides `...xlarge` variants.
6. Image choice depends on the GPU: `DescribeACKPublicImages` entries list supported `vhostType`s. `para.py`
   auto-picks the newest PyTorch image; for `rtx4090.xeon6530.*` (type `rtx4090-pcie`) pass `--image` explicitly.
7. Transient `SSLEOFError` happens a few times per hour: retry (`call()` does). Never auto-retry `CreateServices`.
8. `DescribeACKAvailableResources` returned `[]` for everything; ignore it, rely on `InquiryPrice` / create result.
9. A stopped instance can sit in `Stopping` for 10+ minutes in the API while billing is already stopped; confirm in
   the console/billing page.
10. Do not run `pkill -f blender` / `ps | grep blender` through ssh `exec`: the pattern matches your own shell and
    kills it. Use `pkill -x blender`, and start long jobs via a script file with `nohup ... &`, then poll the log.
11. The terminal on Windows may mangle Chinese API messages; set `PYTHONIOENCODING=utf-8`.

12. **Uploads through the SSH gateway are slow (~13 KB/s)** and a >50 MB upload stalls past tool timeouts. Keep
    uploads small (slim tarballs), use shared storage, or have the instance download from a fast source.
    `github.com` from the instance is slow/times out intermittently; `download.blender.org`, `nodejs.org`,
    `download.nvidia.com` were fine.
13. **Git Bash on Windows rewrites `/root/...` arguments into `C:/Program Files/Git/root/...`.** Export
    `MSYS_NO_PATHCONV=1` before calling `remote.py put/get/run` with absolute remote paths.
14. `remote.py run` with a long job: start it with `nohup ... &` from a script file and poll the log; a foreground
    call that exceeds the tool timeout is killed/backgrounded and leaves half-done state.
15. After `stop` the API can show `Stopping` for 10+ minutes; use `Stopped` as the only "done" signal and check
    billing in the console if it hangs.

## Cost model (measured, synthetic 1080p scene, 3090)
EEVEE 64 spp: 0.55 s/frame -> ~CNY 0.0002/frame. Cycles CUDA 128 spp: 16.9 s/frame -> ~CNY 0.006/frame.
4090 costs 1.45x a 3090 per hour, so it only pays off if it renders >1.45x faster. Cycles: estimated ~2x
(third-party OptiX figures, unmeasured here) -> 4090 cheaper per scene. EEVEE: frame time is dominated by
startup / CPU / disk, so 3090 is cheaper. Real MMD scenes are more CPU-bound than the benchmark; time ~10 real
frames on each GPU before committing to a long render. Use `scripts/bench_scene.py` for a quick GPU check.

## MMD notes (partly tested)
VMDPhysicsBake is tested (see above). Importing PMX/VMD into Blender needs the `mmd_tools` add-on, which is **not
installed in the image yet** and was not tested; install it into `/root/blender` and rebuild the image. Upload
the `.blend`/PMX plus textures with relative paths (or `File > External Data > Pack`).
