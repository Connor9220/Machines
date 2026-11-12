#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-SA-4.0
"""Write index.json for this library of FreeCAD CAM machines: each machine definition (.fcm)
under Resources/Machines, what it is, and the sha256 a download is checked against, with the
sha256 of each earlier version and the commit it was in. Plain Python, no FreeCAD needed: run
it after adding or changing a machine, and commit what it writes.

    python3 tools/make_index.py

FreeCAD lists the machines of every library registered with it and downloads only the one
picked, into the user's Machines folder."""

import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MACHINES = os.path.join("Resources", "Machines")
FORMAT = 1


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def history(path, current):
    """The sha256 of each earlier version of path and the commit it was in, oldest first."""
    found = []
    seen = {current}
    try:
        commits = git("log", "--format=%H", "--follow", "--", path).decode().split()
    except subprocess.CalledProcessError:
        return found
    for commit in reversed(commits):
        try:
            digest = sha256(git("show", "%s:%s" % (commit, path)))
        except subprocess.CalledProcessError:
            continue
        if digest not in seen:
            seen.add(digest)
            found.append({"sha256": digest, "commit": commit})
    return found


def entry(path):
    """The index entry of the machine file at path (relative to ROOT); None if it is not one."""
    with open(os.path.join(ROOT, path), "rb") as f:
        data = f.read()
    try:
        fcm = json.loads(data.decode("utf-8"))
        machine = fcm["machine"]
    except (ValueError, KeyError, TypeError):
        print("left out, not a machine definition:", path, file=sys.stderr)
        return None
    group = os.path.relpath(os.path.dirname(path), MACHINES).replace(os.sep, "/")
    axes = machine.get("axes", {})
    names = list(axes) if isinstance(axes, dict) else []
    item = {
        "id": "%s/%s" % (group, os.path.splitext(os.path.basename(path))[0]),
        "kind": "machine",
        "file": path.replace(os.sep, "/"),
        "size": len(data),
        "sha256": sha256(data),
        "label": machine.get("name") or os.path.splitext(os.path.basename(path))[0],
        "maker": machine.get("manufacturer", ""),
        "description": machine.get("description", ""),
        "group": group,
        "units": machine.get("units", ""),
        "axes": "".join(names),
        "postprocessor": (fcm.get("postprocessor") or {}).get("file_name", ""),
        # whether the file brings the machine's 3D model; a .fcm never does
        "model": False,
    }
    item["history"] = history(item["file"], item["sha256"])
    return item


def main():
    items = []
    for folder, dirs, files in os.walk(os.path.join(ROOT, MACHINES)):
        dirs.sort()
        for name in sorted(files):
            if name.endswith(".fcm"):
                item = entry(os.path.relpath(os.path.join(folder, name), ROOT))
                if item is not None:
                    items.append(item)
    with open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"format": FORMAT, "items": items}, f, indent=1, sort_keys=False)
        f.write("\n")
    print("index.json:", len(items), "machines")


if __name__ == "__main__":
    main()
