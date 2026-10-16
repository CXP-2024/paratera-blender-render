#!/usr/bin/env python3
"""Run commands / transfer files on a Paratera container instance using the cached SSH login.

  remote.py UUID run "<cmd>" [timeout_s]
  remote.py UUID put LOCAL REMOTE
  remote.py UUID get REMOTE LOCAL

Needs `pip install paramiko` (the Windows ssh client cannot take a password non-interactively).
The SSH user is "root@<uuid>" on the gateway host from the cached url (usually port 2222).
"""
import os
import re
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from para_common import load_ssh  # noqa: E402

uuid, op = sys.argv[1], sys.argv[2]
s = load_ssh(uuid)
m = re.match(r"ssh://(?P<user>[^/]+)@(?P<host>[^:@]+):(?P<port>\d+)", s["url"])
cl = paramiko.SSHClient()
cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cl.connect(m["host"], int(m["port"]), username=m["user"], password=s["password"],
           allow_agent=False, look_for_keys=False, timeout=20)
if op == "run":
    t = int(sys.argv[4]) if len(sys.argv) > 4 else 120
    ch = cl.get_transport().open_session()
    ch.set_combine_stderr(True)
    ch.settimeout(t)
    ch.exec_command(sys.argv[3])
    try:
        while True:
            b = ch.recv(4096)
            if not b:
                break
            sys.stdout.write(b.decode(errors="replace"))
            sys.stdout.flush()
    except Exception as e:
        print("[timeout/err]", type(e).__name__)
    print("[exit]", ch.recv_exit_status() if ch.exit_status_ready() else "n/a")
else:
    sf = cl.open_sftp()
    (sf.put if op == "put" else sf.get)(sys.argv[3], sys.argv[4])
    print(op, "ok")
cl.close()
