import platform
import os
import sys

from setuptools import setup


if platform.python_implementation() == "CPython":
    install_requires = ["Cython~=0.29.17"]
else:
    install_requires = []


if sys.version_info < (3, 7, 0):
    raise RuntimeError("extended-jsonschema requires Python 3.7.0+")


with open(os.path.join(os.path.dirname(__file__), "extendedjsonschema", "__init__.py")) as f:
    for line in f:
        if line.startswith("__version__ ="):
            _, _, version = line.partition("=")
            VERSION = version.strip(" \n'\"")
            break
    else:
        raise RuntimeError("Unable to read the version from extendedjsonschema/__init__.py")


with open(os.path.join(os.path.dirname(__file__), "README.md")) as f:
    readme = f.read()


setup(
    name="extended-jsonschema",
    version=VERSION,
    author="Valery Vishnevskiy",
    author_email="v.v.vishnevskiy@yandex.ru",
    url="https://github.com/v-v-vishnevskiy/extended-jsonschema-py",
    project_urls={
        "CI: Travis": "https://travis-ci.org/v-v-vishnevskiy/extended-jsonschema-py",
        "Coverage: codecov": "https://codecov.io/gh/v-v-vishnevskiy/extended-jsonschema-py",
        "GitHub: repo": "https://github.com/v-v-vishnevskiy/extended-jsonschema-py",
    },
    description="A fast JSON Schema validator with extensions",
    long_description=readme,
    long_description_content_type="text/markdown",
    classifiers=[
        "Environment :: Console",
        "Environment :: Web Environment",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    license="MIT",
    keywords=["extended", "json", "jsonschema", "schema", "validator"],
    packages=["extendedjsonschema"],
    provides=["extendedjsonschema"],
    python_requires=">=3.7.0",
    install_requires=install_requires,
)
