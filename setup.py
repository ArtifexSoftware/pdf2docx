'''Build package.'''

import os
from setuptools import find_packages, setup

DESCRIPTION = 'Open source Python library converting pdf to docx.'
EXCLUDE_FROM_PACKAGES = ["build", "dist", "test"]


def get_version(fname):
    '''Read version number from version.txt, created dynamically per Github Action.'''
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            version = f.readline().strip()
    else:
        version = '0.5.6a1'
    return version

def load_long_description(fname):
    '''Load README.md for long description'''
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            long_description = f.read()
    else:
        long_description = DESCRIPTION

    return long_description

def load_requirements(fname):
    '''Load requirements.'''
    try:
        # pip >= 10.0
        from pip._internal.req import parse_requirements
    except ImportError:
        # pip < 10.0
        from pip.req import parse_requirements

    reqs = parse_requirements(fname, session=False)
    try:
        requirements = [str(ir.requirement) for ir in reqs]
    except AttributeError:
        requirements = [str(ir.req) for ir in reqs]
    return requirements


setup(
    name="pdf2docx",
    version=get_version("version.txt"),
    keywords=["pdf-to-word", "pdf-to-docx"],
    description=DESCRIPTION,
    long_description=load_long_description("README.md"),
    long_description_content_type="text/markdown",
    license="GPL v3",
    author='Artifex',
    author_email='support@artifex.com',
    url='https://artifex.com/',
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    include_package_data=True,
    zip_safe=False,
    install_requires=load_requirements("requirements.txt"),
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "pdf2docx=pdf2docx.main:main"
            ]},
)
