import os

def get_version():
    return os.getenv("VERSIONEER_OVERRIDE", default="8.0.beta")
