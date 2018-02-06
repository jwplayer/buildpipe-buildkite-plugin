"""Distutils setup file"""
import textwrap

from setuptools import setup, find_packages

with open('README.rst') as f_readme:
    readme = f_readme.read()

setup(
    name='buildpipe',
    description='Dynamically generate Buildkite pipelines',
    long_description=readme,
    packages=find_packages(exclude=['tests', 'examples']),
    use_scm_version=True,
    author='Kamil Sindi',
    author_email='ksindi@ksindi.com',
    url='https://github.com/ksindi/buildpipe',
    keywords='pipeline buildkite cicd'.split(),
    license='MIT',
    install_requires=[
        'jsonschema>=2.6.0',
        'pyaml>=17.10.0',
        'python-box>=3.1.1',
        'pytz>=2017.2',
    ],
    setup_requires=[
        'pytest-runner',
        'setuptools_scm',
        'sphinx_rtd_theme',
    ],
    tests_require=[
        'freezegun',
        'pytest',
        'pytest-cov',
        'pytest-flake8',
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'buildpipe=buildpipe.__main__:main'
        ]
    },
    classifiers=textwrap.dedent("""
        Development Status :: 5 - Production/Stable
        Intended Audience :: Developers
        License :: OSI Approved :: MIT License
        Environment :: Console
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.6
        """).strip().splitlines(),
)
