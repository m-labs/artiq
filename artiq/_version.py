import os

def get_version():
    override = os.getenv("VERSIONEER_OVERRIDE")
    if override:
      return override
    srcroot = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
    with open(os.path.join(srcroot, "MAJOR_VERSION"), "r") as f:
        version = f.read().strip()
    version += ".unknown"
    if os.path.exists(os.path.join(srcroot, "BETA")):
        version += ".beta"
    return version
