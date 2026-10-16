#!/usr/bin/env python3
"""Paratera (ai.blsc.cn / ai.paratera.com) container-cloud CLI for Blender rendering.

  para.py types [--gpu 1]            list GPU models per zone with live hourly price
  para.py list --zone Z              list your container instances
  para.py create --zone Z --model M --yes     create (BILLS MONEY; --yes required)
  para.py ssh --zone Z --uuid U      fetch SSH login, cache it locally (password not printed)
  para.py stop --zone Z --uuid U     stop + stop charging, wait until Stopped
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from para_common import call, profiles, save_ssh  # noqa: E402


def clients():
    from ack_product.ACKProductClientMain import ACKProductClient
    from ackcs.ACKCSClientMain import ACKCSClient

    hp, cp = profiles()
    return ACKProductClient(hp, cp), ACKCSClient(hp, cp)


def pick_image(images, zone, svc_type):
    c = [i for i in images if i["zone"]["zoneCode"] == zone and svc_type in (i.get("vhostType") or "").split(",")]
    py = [i for i in c if i.get("platformName") == "PyTorch"] or c
    py.sort(key=lambda i: i.get("platformVersion") or "", reverse=True)
    return py[0]["imageUuid"] if py else None


def body(zone, model, image, name):
    return {"zoneCode": zone, "serviceModel": model, "imageUuid": image, "count": 1,
            "billingType": "PostPaid", "aliasName": name}


def cmd_types(a):
    prod, cs = clients()
    types = call(prod, "DescribeACKServiceTypes", {})["data"]
    images = call(prod, "DescribeACKPublicImages", {})["data"]
    for t in types:
        if a.gpu and t["serviceGpus"] != a.gpu:
            continue
        z, m = t["zone"]["zoneCode"], t["serviceModel"]
        img = pick_image(images, z, t["serviceType"])
        price = "?"
        if img:
            r = call(cs, "InquiryPriceCreateServices", body(z, m, img, "q"))
            price = (r.get("data") or {}).get("originPrice", "?")
        print("%-16s %-40s gpus=%s cpu=%s mem=%sG  CNY/h=%s  image=%s" % (
            z, m, t["serviceGpus"], t["serviceCpus"], t["serviceMemory"] // 2**30, price, img))


def cmd_list(a):
    _, cs = clients()
    for r in call(cs, "DescribeServices", {"zoneCode": a.zone})["data"]["rows"] or []:
        print(r["serviceUuid"], r.get("aliasName"), r["serviceStatus"])


def cmd_create(a):
    prod, cs = clients()
    img = a.image or pick_image(call(prod, "DescribeACKPublicImages", {})["data"], a.zone, a.model.split(".")[0])
    if not img:
        sys.exit("no image found; pass --image")
    b = body(a.zone, a.model, img, a.name)
    price = call(cs, "InquiryPriceCreateServices", b)["data"]
    print("price CNY/h:", price.get("originPrice"), "balance:", price.get("cashBalance"))
    if not a.yes:
        sys.exit("dry run only. Re-run with --yes to actually create (starts billing).")
    r = call(cs, "CreateServices", b, retries=1)  # never blind-retry a create
    uuid = r["data"][0]["resourceUuid"]
    print("created", uuid)
    for _ in range(60):
        st = {x["serviceUuid"]: x["serviceStatus"] for x in call(cs, "DescribeServices", {"zoneCode": a.zone})["data"]["rows"]}
        print(" ", st.get(uuid), flush=True)
        if st.get(uuid) == "Running":
            break
        time.sleep(10)
    cmd_ssh(argparse.Namespace(zone=a.zone, uuid=uuid))


def cmd_ssh(a):
    _, cs = clients()
    s = call(cs, "DescribeServicesSSH", {"zoneCode": a.zone, "serviceUuids": [a.uuid]})["data"]["sshes"][0]
    p = save_ssh(a.uuid, s)
    print("ssh url:", s["url"], "\npassword cached (not printed) in", p)


def cmd_stop(a):
    _, cs = clients()
    print("stop code:", call(cs, "StopServices", {"zoneCode": a.zone, "serviceUuids": [a.uuid],
                                                  "saveEnv": False, "stoppedMode": 1})["code"])
    for _ in range(60):
        st = {x["serviceUuid"]: x["serviceStatus"] for x in call(cs, "DescribeServices", {"zoneCode": a.zone})["data"]["rows"]}
        print(" ", st.get(a.uuid), flush=True)
        if st.get(a.uuid) not in ("Running", "Stopping"):
            return
        time.sleep(10)
    print("still Stopping after 10 min - verify in the console that billing stopped")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("types"); p.add_argument("--gpu", type=float, default=1.0); p.set_defaults(f=cmd_types)
p = sub.add_parser("list"); p.add_argument("--zone", required=True); p.set_defaults(f=cmd_list)
p = sub.add_parser("create")
p.add_argument("--zone", required=True); p.add_argument("--model", required=True)
p.add_argument("--name", default="blender-render"); p.add_argument("--image"); p.add_argument("--yes", action="store_true")
p.set_defaults(f=cmd_create)
p = sub.add_parser("ssh"); p.add_argument("--zone", required=True); p.add_argument("--uuid", required=True); p.set_defaults(f=cmd_ssh)
p = sub.add_parser("stop"); p.add_argument("--zone", required=True); p.add_argument("--uuid", required=True); p.set_defaults(f=cmd_stop)
a = ap.parse_args()
a.f(a)
