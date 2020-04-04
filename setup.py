"""Distutils setup file"""
import textwrap

from setuptools import setup, find_packages

with open("README.md") as f_readme:
    readme = f_readme.read()

with open("requirements.txt") as f:
    install_requires = f.read().splitlines()

setup(
    name="buildpipe",
    description="Dynamically generate Buildkite pipelines",
    long_description=readme,
    packages=find_packages(exclude=["tests"]),
    use_scm_version=True,
    author="Kamil Sindi",
    author_email="kamil@jwplayer.com",
    url="https://github.com/jwplayer/buildpipe",
    keywords="pipeline buildkite buildkite-plugin cicd".split(),
    license="MIT",
    install_requires=install_requires,
    setup_requires=["pytest-runner", "setuptools_scm",],
    tests_require=["pytest", "pytest-cov", "pytest-flake8",],
    include_package_data=True,
    zip_safe=False,
    entry_points={"console_scripts": ["buildpipe=buildpipe.__main__:main"]},
    classifiers=textwrap.dedent(
        """
        Development Status :: 5 - Production/Stable
        Intended Audience :: Developers
        License :: OSI Approved :: MIT License
        Environment :: Console
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.6
        Programming Language :: Python :: 3.7
        Programming Language :: Python :: 3.8
        """
    )
    .strip()
    .splitlines(),
)
