#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages

from scripts.setup_utils import read_version, write_version, get_rpm_version


project_name = "schedules-tools"
project_url = "https://github.com/RedHat-Eng-PGM/python-schedules-tools"
project_author = "Red Hat, Inc."
project_author_email = "pp-dev-list@redhat.com"
project_description = "Schedules tools to handle/convert various schedule formats"
package_name = project_name


# VERSION - write version only when building from git
package_version = ['5.30.0', 1, 'git']  # default
save_version_dirs = ["schedules_tools"]

if os.path.isdir(".git"):
    # we're building from a git repo -> store version tuple to __init__.py
    if package_version[2] == "git":
        force = True
        package_version[0], package_version[1], package_version[2] = get_rpm_version()

    for i in save_version_dirs:
        file_name = os.path.join(i, "version.py")
        write_version(file_name, package_version)
else:  # see if there is already saved version
    for i in save_version_dirs:
        file_name = os.path.join(i, "version.py")
        version = read_version(file_name)
        if version:
            package_version = list(version)
            break


with open('requirements.txt') as fd:
    requirements = fd.read().split()

with open('requirements-tests.txt') as fd:
    requirements_tests = fd.read().split()

py_version = sys.version[:1]

setup(
    name=package_name,
    url=project_url,
    version='.'.join([str(v) for v in package_version[0:2]]),
    license='GPL',
    author=project_author,
    author_email=project_author_email,
    description=project_description,
    packages=find_packages(exclude=('scripts',)),
    include_package_data=True,
    tests_require=requirements_tests,
    entry_points={
        # Make them all start with schedule- and end with python version
        #   so we can generate symlinks in /usr/bin/ post install
        'console_scripts': [
            'schedule-convert%s=schedules_tools.bin.schedule_convert:main' % py_version,
            'schedule-diff%s=schedules_tools.bin.schedule_diff:main' % py_version,
        ]
    },
    install_requires=requirements,
)
