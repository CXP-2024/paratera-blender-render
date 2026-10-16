"""Shared helpers: credentials, generic API calls with retry, local state dir."""
import json
import os
import time

STATE_DIR = os.path.expanduser(os.environ.get("PARA_STATE_DIR", "~/.paratera"))


def _read(path):
    return open(os.path.expanduser(path), encoding="utf-8-sig").read().strip()


def profiles():
    """AK/SK come from files (never printed). Override paths with PARA_AK_FILE / PARA_SK_FILE."""
    from common.ClientProfileMain import ClientProfile
    from common.HttpProfileMain import HttpProfile

    ak = _read(os.environ.get("PARA_AK_FILE", "~/.ssh/para_ak"))
    sk = _read(os.environ.get("PARA_SK_FILE", "~/.ssh/para_sk"))
    return HttpProfile(), ClientProfile(ak, sk)


def call(client, action, body, retries=6):
    """Raw JSON call. The SDK request classes are broken (class attrs shadow dict keys),
    so always pass plain dicts through GenericRequest. Retries on transient SSL EOF errors."""
    for _ in range(retries):
        try:
            return client.GenericRequest(body, action, lambda j: j)
        except Exception as e:  # SDK wraps requests errors in AICloudException
            print("  retry %s (%s)" % (action, type(e).__name__), flush=True)
            time.sleep(5)
    raise RuntimeError("giving up on " + action)


def save_ssh(uuid, ssh):
    os.makedirs(STATE_DIR, exist_ok=True)
    p = os.path.join(STATE_DIR, "ssh_%s.json" % uuid)
    json.dump(ssh, open(p, "w"))
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def load_ssh(uuid):
    return json.load(open(os.path.join(STATE_DIR, "ssh_%s.json" % uuid)))
