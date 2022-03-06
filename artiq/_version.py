import os

def get_version():
    return os.getenv("VERSIONEER_OVERRIDE", default="7.0.beta")
