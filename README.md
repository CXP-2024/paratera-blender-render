# paratera-blender-render

An agent skill (Claude Code `SKILL.md` format) for rendering Blender / MMD animations on rented GPU containers
from Paratera (并行科技 智算云 container cloud): create an instance via the Python SDK, install headless Blender
with working GPU EEVEE/Cycles, render over SSH, and stop the instance.

- `SKILL.md` - the skill (instructions, gotchas, cost model)
- `scripts/para.py` - list models/prices, create (dry-run by default), fetch SSH login, stop
- `scripts/remote.py` - run commands and transfer files over SSH (paramiko)
- `scripts/setup_instance.sh` - installs Blender and the NVIDIA GL/EGL/OptiX userspace libs on the instance
- `scripts/patch_sdk.py` - fixes `_sha256` import in the vendor SDK on Python >= 3.12
- `scripts/bench_scene.py` - synthetic scene for timing EEVEE / Cycles

The vendor SDK wheel (`aicloud_sdk_python-3.0`) and all credentials are intentionally **not** included.

Install as a skill: copy this folder to `~/.claude/skills/paratera-blender-render/`.
