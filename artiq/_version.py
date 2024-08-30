import os

def get_rev():
    return os.getenv("VERSIONEER_REV", default="unknown")

def get_version():
    return os.getenv("VERSIONEER_OVERRIDE", default="10.0+unknown.beta")

