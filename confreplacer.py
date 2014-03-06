#!/usr/bin/env python
# -*- coding: utf-8 -*-
# confreplacer.py

import sys
from optparse import OptionParser
import subprocess
from path import path
import filecmp
from exceptions import RuntimeError



def run(cmd):
    """Execute 'cmd' in a shell. Return exit status.
    """
    return subprocess.call(cmd, shell=True)




class ConfReplacer:

    def __init__(self, base_dir, initd, nagios_bin):
        self.base_dir = base_dir
        self.initd = initd
        self.bin = nagios_bin

        self.dst_dir = path.joinpath(self.base_dir, 'naginator.d')
        self.bak_dir = path.joinpath(self.base_dir, 'backup.d')
        self.tmp_dir = path.joinpath(self.base_dir, 'tmp.d')


    def generate(self, url, nagios_types):
        """Generate a new configuration in a temporary place.
        """
        # Get destination directories ready.
        self._clean()
        path(self.tmp_dir).mkdir_p(0755)

        # Generate configuration for every Nagios_type.
        results = []
        cmd = '''naginator.py -i %s --stdout -r %s > %s'''
        for obj in nagios_types:
            r = run(cmd % (url, obj, self.tmp_dir.joinpath('%s.conf' % obj)))
            results.append(r)

        if any(results):
            raise RuntimeError('Errors while generating new configuration.')



    def push(self, noop=False):
        """Replace existing configuration with generated configuration.

        Only acts if there are changes and the new configuration is valid.
        """
        if self._has_changes():
            if not noop:
                self._replace()
                if self._is_valid():
                    self._reload()
                    self._clean()
                else:
                    self._rollback()
        else:
            self._clean()


    def _clean(self):
        self.tmp_dir.rmtree_p()
        self.bak_dir.rmtree_p()


    def _has_changes(self):
        diff_dir = filecmp.dircmp(self.tmp_dir, self.dst_dir)
        changes = diff_dir.diff_files + diff_dir.left_only + diff_dir.right_only
        return changes != []


    def _is_valid(self):
        # [todo] Check there are no empty files.
        conf_file = path.joinpath(self.base_dir, 'nagios.cfg')
        cmd = '%s -v %s > /dev/null 2>&1' % (self.bin, conf_file)
        return run(cmd) == 0


    def _replace(self):
        self.dst_dir.move(self.bak_dir)
        self.tmp_dir.move(self.dst_dir)


    def _rollback(self):
        self.dst_dir.move(self.tmp_dir)
        self.bak_dir.move(self.dst_dir)
        raise RuntimeError('Something is wrong in the generated configuration (look at tmp.d/)')


    def _reload(self):
        run('''%s reload > /dev/null 2>&1''' % self.initd)




def main():
    usage = """Usage: %prog [options]

    Resource types:

    command contact contactgroup host hostdependency hostescalation hostextinfo
    hostgroup service servicedependency serviceescalation serviceextinfo
    servicegroup timeperiod
    """
    parser = OptionParser(usage)
    parser.add_option("-i", "--hostname", dest="hostname",
                      help="Hostname or IP of PuppetDB host.")
    parser.add_option("-r", "--resources", dest="resources",
            help="""Comma-separated list of Nagios resources [default: all]""")
    parser.add_option("-b", "--bin", help="Nagios binary [default: %default]",
                      type="string", dest="bin", default="/usr/bin/nagios")
    parser.add_option("-d", "--initd", help="Nagios init.d script [default: %default]",
                      type="string", dest="initd", default='/etc/init.d/nagios')
    parser.add_option("--base-dir", help="Base configuration directory [default: %default]",
                      type="string", dest="base_dir", default="/etc/nagios")
    parser.add_option("-w", "--write", help="Location of config to write to [default: %default]",
                      action="store", type="string", dest="confwrite",
                      default='/etc/nagios/nagios.cfg')

    (opts, args) = parser.parse_args()

    all_resource_types = ['command', 'contact', 'contactgroup', 'host', 'hostdependency',
        'hostescalation', 'hostextinfo', 'hostgroup', 'service', 'servicedependency',
        'serviceescalation', 'serviceextinfo', 'servicegroup', 'timeperiod']

    if not opts.hostname:
        print "Please provide a hostname."
        sys.exit(1)

    if opts.resources:
        opts.resources = opts.resources.split(',')
    else:
        opts.resources = all_resource_types


    replacer = ConfReplacer(opts.base_dir, opts.initd, opts.bin)
    replacer.generate(opts.hostname, opts.resources)
    replacer.push(noop=False)


if __name__ == '__main__':
    main()

