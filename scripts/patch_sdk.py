"""aicloud-sdk-python 3.0 imports `_sha256`, which does not exist on Python >= 3.12.
Patch the installed file to use hashlib. Idempotent. Run once after installing the wheel."""
import importlib.util
import os
import sys

spec = importlib.util.find_spec("common")
if spec is None or not spec.submodule_search_locations:
    sys.exit("aicloud SDK not installed (pip install aicloud_sdk_python-3.0-py3-none-any.whl)")
path = os.path.join(list(spec.submodule_search_locations)[0], "utils", "SignUtils.py")
src = open(path, encoding="utf-8").read()
if "from _sha256 import sha256" in src:
    open(path, "w", encoding="utf-8").write(src.replace("from _sha256 import sha256", "from hashlib import sha256"))
    print("patched", path)
else:
    print("already fine:", path)
