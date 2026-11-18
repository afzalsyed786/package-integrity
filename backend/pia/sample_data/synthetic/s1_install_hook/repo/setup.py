from setuptools import find_packages, setup

setup(
    name="colorfmt-synth",
    version="1.4.2",
    description="Tiny ANSI colour formatting helpers (PIA synthetic demo)",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
)
