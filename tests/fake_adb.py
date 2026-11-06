"""Stand-in for the adb binary, used by the tests. The TV filesystem lives in $FAKE_ADB_ROOT.

Behaviour switches (files in the root directory):
  offline   -> device not authorized / offline
  hang      -> every command sleeps (to test timeouts)
  corrupt   -> pushed files are altered (to test checksum verification)
  no-kodi   -> Kodi is not installed
Every invocation is appended to commands.log.
"""
import hashlib
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

root = Path(os.environ["FAKE_ADB_ROOT"])
args = sys.argv[1:]
with open(root / "commands.log", "a") as log:
    log.write(" ".join(args) + "\n")

if (root / "hang").exists():
    time.sleep(30)


def tv(path: str) -> Path:
    return root / path.lstrip("/")


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


if args and args[0] == "connect":
    print(f"failed to connect to {args[1]}" if (root / "offline").exists()
          else f"connected to {args[1]}")
    sys.exit(0)
if args[:1] == ["-s"]:
    args = args[2:]
if (root / "offline").exists():
    fail("error: device offline")

cmd = args[0]
if cmd == "get-state":
    print("device")
elif cmd == "forward":
    print(args[1].split(":")[1])
elif cmd == "push":
    dst = tv(args[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(args[1], dst)
    if (root / "corrupt").exists():
        with open(dst, "ab") as f:
            f.write(b"garbage")
    print(f"{args[1]}: 1 file pushed")
elif cmd == "pull":
    if not tv(args[1]).exists():
        fail(f"adb: error: remote object '{args[1]}' does not exist")
    if tv(args[1]).is_dir():
        shutil.copytree(tv(args[1]), args[2])
    else:
        shutil.copy(tv(args[1]), args[2])
elif cmd == "install":
    (root / "no-kodi").unlink(missing_ok=True)
    print("Success")
elif cmd == "shell":
    line = args[1]
    words = shlex.split(line.split("|")[0])
    if line.startswith("[ -e "):
        print("yes" if tv(words[2]).exists() else "no")
    elif words[0] == "sha256sum":
        p = tv(words[1])
        if not p.exists():
            fail(f"sha256sum: {words[1]}: No such file or directory")
        print(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {words[1]}")
    elif words[:2] == ["mkdir", "-p"]:
        tv(words[2]).mkdir(parents=True, exist_ok=True)
    elif words[:2] == ["mv", "-f"]:
        os.replace(tv(words[2]), tv(words[3]))
    elif words[:2] == ["ls", "-1"]:
        print("\n".join(sorted(p.name for p in tv(words[2]).iterdir())))
    elif words[0] == "cp":
        if not tv(words[2]).exists():  # like Kodi's app folder: files can be replaced, not created
            fail(f"cp: {words[2]}: Permission denied")
        shutil.copy(tv(words[1]), tv(words[2]))
    elif line == "cat /proc/meminfo":
        print("MemTotal:        1807396 kB\nMemFree:           84552 kB\nMemAvailable:     670120 kB")
    elif words[:2] == ["df", "-k"]:
        print("Filesystem 1K-blocks Used Available Use% Mounted on\n"
              "/dev/fuse 8283280 5487240 2796040 67% /storage/emulated")
    elif words[:2] == ["dumpsys", "meminfo"]:
        print("           TOTAL PSS:   174123            TOTAL RSS:   250000")
    elif words[:2] == ["rm", "-f"]:
        tv(words[2]).unlink(missing_ok=True)
    elif words[0] == "getprop":
        print({"ro.build.version.release": "12", "ro.product.cpu.abi": "armeabi-v7a"}
              .get(words[1], ""))
    elif words[:2] == ["dumpsys", "package"]:
        installed = not (root / "no-kodi").exists()
        if installed and "versionName" in line:
            print("    versionName=21.3")
        elif installed and "READ_EXTERNAL_STORAGE" in line:
            print("      android.permission.READ_EXTERNAL_STORAGE: granted=true")
    elif words[0] in ("pidof", "am", "monkey", "input"):
        pass
    else:
        fail(f"fake adb: unsupported shell command: {line}")
else:
    fail(f"fake adb: unsupported command: {args}")
