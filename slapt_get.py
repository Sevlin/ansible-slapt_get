#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2017, Mykyta Solomko
# Written by Mykyta Solomko <sev@nix.org.ua>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.
#

DOCUMENTATION = '''
---
'''

EXAMPLES = '''
'''

import os
import sys
from ansible.module_utils.basic import *

module = AnsibleModule(
    argument_spec = dict(
        package = dict(
            type     = 'list',
            aliases  = ['pkg', 'name'],
            default  = None
        ),
        state = dict(
            type     = 'str',
            choices  = ['absent', 'present', 'installed', 'removed', 'latest'],
            default  = 'present'
        ),
        upgrade      = dict(
            type     = 'str',
            choices  = ['yes', 'no', 'dist'],
            default  = 'no'
        ),
        install_set  = dict(
            type     = 'bool',
            aliases  = ['install-set'],
            default  = False
        ),
        suggested    = dict(
            type     = 'bool',
            aliases  = ['install-suggested'],
            default  = False
        ),
        add_gpg_keys = dict(
            type     = 'bool',
            aliases  = ['add-gpg', 'add-keys'],
            default  = False
        ),
        update_cache = dict(
            type     = 'bool',
            aliases  = ['update-cache', 'update'],
            default  = False
        ),
        clean_cache = dict(
            type     = 'str',
            aliases  = ['clean-cache', 'clean'],
            choices  = ['all', 'yes', 'old', 'no'],
            default  = 'no'
        ),
        gpg_check = dict(
            type     = 'bool',
            aliases  = ['gpg-check'],
            default  = True
        ),
        ignore_excludes = dict(
            type     = 'bool',
            aliases  = ['ignore-excludes'],
            default  = False
        ),
        ignore_deps = dict(
            type     = 'bool',
            aliases  = ['ignore-deps'],
            default  = False
        ),
        ignore_checksum = dict(
            type     = 'bool',
            aliases  = ['ignore-checksum', 'ignore-md5'],
            default  = False
        ),
    ),
    mutually_exclusive = [['package', 'upgrade']],
    required_one_of = [['package', 'upgrade', 'update_cache']],
    supports_check_mode = True
)


module.run_command_environ_update = dict(
        LANG = 'C',
        LC_ALL = 'C',
        LC_MESSAGES = 'C',
        LC_CTYPE = 'C',
)


def is_installed(name, state):

    # Add sorting parameters to check if the package is the latest version available
    # otherwise leave cmd_sort_params varable empty to find out weather the package is installed
    if state == "latest":
        cmd_get_latest = '| sort -V -r | head -1 '

    # Query the package
    rc, _, _ = module.run_command(' '.join([
            slaptget_path, slaptget_flags, '--search', package,
            '|', 'egrep', "'^{0}-.*'".format(name),
            cmd_sort_params,
            '|', 'grep', '-q' 'inst=yes'
            ])
        )

    # Package is installed/latest
    if rc == 0:
        return True

    return False


def slapt_exec(slaptget_action, simulate, name):

    slaptget_simulate = ''

    if simulate:
        slaptget_simulate = '--simulate'

    rc, out, err = module.run_command(' '.join([
                slaptget_path, slaptget_flags, slaptget_simulate, slaptget_action, name
            ])
        )

    return {'rc':rc, 'out':out, 'err':err}


# Update packages list
def slapt_update():

    ret = slapt_exec('--update', False, '')

    if ret['rc'] != 0:
        module.fail_json(
            msg = 'Failed to update cache',
            rc  = ret['rc'],
            err = ret['err']
        )


# Clean package cache
def slapt_clean():

    # Remove all cached packages
    slaptget_action = '--clean'

    # Remove only old/unreachable packages
    if module.params['clean_cache'] == 'old':
        slaptget_action = '--autoclean'

    ret = slapt_exec(slaptget_action, False, '')

    if ret['rc'] != 0:
        module.fail_json(
            msg = 'Failed to clean cache',
            rc  = ret['rc'],
            err = ret['err']
        )


# Add GPG keys
def slapt_add_keys():
    ret = slapt_exec('--add-keys', False, '')

    if ret['rc'] != 0:
        module.fail_json(
            msg = 'Failed to clean cache',
            rc  = ret['rc'],
            err = ret['err']
        )


# Install package
def slapt_install(name):

    # Don't attempt to upgrade installed package
    # if state is 'present' or 'installed'
    if (( module.params['upgrade'] == 'no' and module.params['state'] != 'latest' )):
        slaptget_action = '--install --no-upgrade'

    # Install upgraded version of the package
    else:
        slaptget_action = '--install'

    ret = slapt_exec(slaptget_action, module.check_mode, name)

    if ret['rc'] != 0:
        module.fail_json(
            msg = 'Failed to install package {}'.join(name),
            rc  = ret['rc'],
            err = ret['err']
        )

# Remove package
def slapt_remove(name):

    ret = slapt_exec('--remove --no-dep', module.check_mode, name)

    if ret['rc'] != 0:
        module.fail_json(
            msg = 'Failed to remove package {}'.join(name),
            rc  = ret['rc'],
            err = ret['err']
        )


def parse_package_list(plain_text):
    if len(plain_text) > 0:

        import re

        re_pkg_install = re.compile("^The following NEW packages will be installed:")
        re_pkg_upgrade = re.compile("^The following packages will be upgraded:")
        re_pkg_remove  = re.compile("^The following packages will be REMOVED:")
        re_pkg_suggest = re.compile("^Suggested packages:")
        re_pkg_list = re.compile("^\s{2}(\S+|\s)+")

        packages = {'install':'', 'upgrade':'', 'remove':'', 'devnull':''}
        section = ''

        for line in plain_text.splitlines():
            if re_pkg_list.match(line):
                packages[section] += line

            elif re_pkg_install.match(line):
                section = 'install'

            elif re_pkg_upgrade.match(line):
                section = 'upgrade'

            elif re_pkg_remove.match(line):
                section = 'remove'

            elif (( module.params['suggested'] and re_pkg_suggest.match(line) )):
                section = 'install'

            else:
                section = 'devnull'

    packages['install'] = packages['install'].strip().split()
    packages['upgrade'] = packages['upgrade'].strip().split()
    packages['remove']  = packages['remove'].strip().split()

    return [packages['install'], packages['upgrade'], packages['remove']]



def query_packages(packages, state):

    to_install = []
    to_upgrade = []
    to_remove  = []

    if packages:
        if module.params['install_set']:
            ret = slapt_exec('--install-set', True, ' '.join(packages))

        elif module.params['state'] in ['installed', 'present', 'latest']:
            ret = slapt_exec('--install', True, ' '.join(packages))

        elif module.params['state'] in ['absent', 'removed']:
            ret = slapt_exec('--remove', True, ' '.join(packages))

    """
    Upgrade section:
    - Regular package upgrade
    - Distribution upgrade
    """
    if module.params['upgrade'] == 'yes':
        ret = slapt_exec('--upgrade', True, '')

    elif module.params['upgrade'] == 'dist':
        ret = slapt_exec('--dist-upgrade', True, '')


    try:
        ret['out']
    except NameError:
        return [to_install, to_upgrade, to_remove]
    else:
        to_install, to_upgrade, to_remove = parse_package_list(ret['out'])

        """
        Remove duplicates
        """
        set(to_install)
        set(to_upgrade)
        set(to_remove)

    return [to_install, to_upgrade, to_remove]


def main():
    global slaptget_path
    slaptget_path = '/usr/sbin/slapt-get'

    global slaptget_flags
    slaptget_flags = '--no-prompt'

    package      = module.params.get('package')
    state        = module.params.get('state')

    state_chaneged = False

    to_install = []
    to_upgrade = []
    to_remove  = []


    if not module.params['gpg_check']:
        slaptget_flags += ' --allow-unauthenticated'

    if module.params['ignore_deps']:
        slaptget_flags += ' --no-dep'

    if module.params['ignore_checksum']:
        slaptget_flags += ' --no-md5'


    if module.params['update_cache']:
        slapt_update()

    if module.params['clean_cache']:
        slapt_clean()

    if module.params['add_gpg_keys']:
        slapt_add_keys()

    to_install, to_upgrade, to_remove = query_packages(package, state)

    """
    install/upgrade/remove packages
    """
    if not module.check_mode:
        if to_install:
            for pkg in to_install:
                slapt_install(pkg)
            state_chaneged = True

        if to_upgrade:
            for pkg in to_upgrade:
                slapt_install(pkg)
            state_chaneged = True

        if to_remove:
            for pkg in to_remove:
                slapt_remove(pkg)
            state_chaneged = True


    module.exit_json(changed = state_chaneged, packages = {"installed": to_install, "upgraded": to_upgrade, "removed": to_remove})

if __name__ == '__main__':
    main()

