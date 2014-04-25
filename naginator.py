#!/usr/bin/env python

import sys
import os
import subprocess
import json
import difflib
from optparse import OptionParser
import filecmp
from os.path import join, exists
from shutil import rmtree, move
from exceptions import RuntimeError
try:
    import jinja2
except:
    print "Please install python-jinja2."
    sys.exit(1)
try:
    import requests
except:
    print "Please install python-requests."
    sys.exit(1)

__author__ = "Vladimir Lazarenko, Metin de Vreugd"
__version__ = "1.0.0"
__date__ = "12-14-2012"
__maintainer__ = "SiteOps eBay Classifieds"
__email__ = "favoretti@gmail.com"
__status__ = "Testing"


def run(cmd):
    """Execute 'cmd' in a shell. Return exit status.
    """
    return subprocess.call(cmd, shell=True)


class NagiosConf:

    def __init__(self, url, dtype, base_dir, single_config=False, tag=''):

        self.tmpl = """{% set bad_params = ['notify', 'target', 'ensure', 'require', 'before', 'tag'] -%}
{% for element in elements %}
define {{ dtype }} {
{% if title_var -%}
  {{ title_var.ljust(31)|indent(8,true) }}{{ element['title'] }}{{ "\n" }}
{%- endif -%}
{%- for key, value in element['parameters']|dictsort -%}
  {%- if key not in bad_params -%}
    {{ key.ljust(31)|indent(8,true) }}{{ value|join("") }}{{ "\n" }}
  {%- endif -%}
{% endfor -%}
}
{% endfor %}
"""
        self.url = url
        self.dtype = dtype
        self.base_dir = base_dir
        self.tmp_dir = os.path.join(self.base_dir, 'tmp.d')
        self.tag = tag
        self.single_config = single_config

    def get_nagios_data(self, exported=True):
        """ Function for fetching data from PuppetDB """
        if exported:
            if self.tag:
                query = """["and",
                    ["=", "exported",  true],
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", "tag", "{tag}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype,
                                                               tag=self.tag)
            else:
                query = """["and",
                    ["=", "exported",  true],
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype)
        else:
            if self.tag:
                query = """["and",
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", "tag", "{tag}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype,
                                                               tag=self.tag)
            else:
                query = """["and",
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype)

        headers = {'Accept': 'application/json'}
        # Specify an order for the resources, so we can compare (diff) results from several runs.
        payload = {'query': query, 'order-by': '[{"field": "title"}]'}
        r = requests.get(self.url, params=payload, headers=headers)
        ndata = json.loads(r.text)
        return ndata

    def get(self):
        """Returns a python object with Nagios objects of type 'dtype'.
        """
        titles = {
            'command': 'command_name',
            'contact': 'contact_name',
            'contactgroup': 'contactgroup_name',
            'host': 'host_name',
            'hostextinfo': 'host_name',
            'hostgroup': 'hostgroup_name',
            'servicegroup': 'servicegroup_name',
            'timeperiod': 'timeperiod_name',
        }
        return jinja2.Template(self.tmpl).render(
            dtype=self.dtype,
            elements=self.get_nagios_data(),
            title_var=titles.get(self.dtype))

    def write(self):
        """Write config to a file in tmp.d/. File is named afther the Nagios type.
        """
        if self.single_config:
            write_mode = 'a'
            conf_file = os.path.join(self.tmp_dir, '%s.cfg' % self.single_config)
        else:
            write_mode = 'w'
            conf_file = os.path.join(self.tmp_dir, '%s.cfg' % self.dtype)

        if not os.path.exists(self.tmp_dir):
            try:
                os.mkdir(self.tmp_dir)
            except Exception, e:
                print "Can not create temporary directory ({tmpdir}): " \
                    "{exception}.\nExiting.".format(tmpdir=self.tmp_dir, exception=e)
                sys.exit(1)
        config = self.get()
        with open(conf_file, write_mode) as f:
            f.write(config)


class ConfReplacer:

    def __init__(self, base_dir, initd, nagios_bin, print_changes):
        self.base_dir = base_dir
        self.initd = initd
        self.bin = nagios_bin
        self.print_changes = print_changes

        self.dst_dir = join(self.base_dir, 'naginator.d')
        self.bak_dir = join(self.base_dir, 'backup.d')
        self.tmp_dir = join(self.base_dir, 'tmp.d')

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
        if exists(self.tmp_dir):
            rmtree(self.tmp_dir)
        if exists(self.bak_dir):
            rmtree(self.bak_dir)

    def _has_changes(self):
        if not exists(self.tmp_dir) or not exists(self.dst_dir):
            return True

        diff_dir = filecmp.dircmp(self.tmp_dir, self.dst_dir)
        changes = diff_dir.diff_files + diff_dir.left_only + diff_dir.right_only

        if self.print_changes:
            if len(changes):
                print 'Changed files:'
            for changed_file in changes:
                if changed_file in diff_dir.left_only:
                    print 'File {0} is new.'.format(changed_file)
                    continue

                if changed_file in diff_dir.right_only:
                    print 'File {0} is removed.'.format(changed_file)
                    continue

                print '*** {0}/{1}'.format(self.dst_dir, changed_file)
                for line in difflib.unified_diff(open('{0}/{1}'.format(self.dst_dir, changed_file)).readlines(),
                        open('{0}/{1}'.format(self.tmp_dir, changed_file)).readlines()):
                    sys.stdout.write(line)
        return changes != []

    def _is_valid(self):
        # [todo] Check there are no empty files.
        conf_file = join(self.base_dir, 'nagios.cfg')
        if not exists(self.bin):
            raise RuntimeError("Can not find nagios binary: {0}".format(self.bin))

        cmd = '%s -v %s > /dev/null 2>&1' % (self.bin, conf_file)
        return run(cmd) == 0

    def _replace(self):
        if exists(self.bak_dir):
            rmtree(self.bak_dir)

        if exists(self.dst_dir):
            move(self.dst_dir, self.bak_dir)
        move(self.tmp_dir, self.dst_dir)

    def _rollback(self):
        if exists(self.tmp_dir):
            rmtree(self.tmp_dir)
        move(self.dst_dir, self.tmp_dir)
        if exists(self.bak_dir):
            if exists(self.dst_dir):
                rmtree(self.dst_dir)
            move(self.bak_dir, self.dst_dir)
        raise RuntimeError('Something is wrong in the generated configuration (look at tmp.d/)')

    def _reload(self):
        run('''%s reload > /dev/null 2>&1''' % self.initd)


def main():
    usage = '''Usage: %prog [options]

    Resource types:

    command contact contactgroup host hostdependency hostescalation hostextinfo
    hostgroup service servicedependency serviceescalation serviceextinfo
    servicegroup timeperiod
'''
    parser = OptionParser(usage)
    parser.add_option("-i", "--hostname", dest="hostname",
        help="Hostname or IP of PuppetDB host.")
    parser.add_option("-r", "--resources", dest="resources",
                      help="""Comma-separated list of Nagios resources
                              [default: all]""")
    parser.add_option("-t", "--tag", dest="tag",
                      help="Only resources with this tag.")
    parser.add_option("--base-dir", type="string", dest="base_dir", default="/etc/nagios",
                      help="Base configuration directory [default: %default]")
    parser.add_option("-b", "--bin", type="string", dest="bin", default="/usr/bin/nagios",
                      help="Nagios binary [default: %default]")
    parser.add_option("-d", "--initd", type="string", dest="initd", default='/etc/init.d/nagios',
                      help="Nagios init.d script [default: %default]")
    parser.add_option("--noop", action="store_true", default=False,
                      help="Generate new config on tmp.d/ but don't apply it.")
    parser.add_option("--single-config", dest="single_config", default=False,
                      help="Place all configuration in a single file.")
    parser.add_option("--print-changes", dest="print_changes", action="store_true", default=False,
                      help="Print unified diff of changed configuration files.")

    (opts, args) = parser.parse_args()

    if opts.hostname:
        url = "http://" + opts.hostname + ":8080/v3/resources"
    else:
        print "Please provide a hostname."
        sys.exit(1)

    if opts.resources:
        opts.resources = opts.resources.split(',')
    else:
        opts.resources = ['command', 'contact', 'contactgroup', 'host',
                          'hostdependency', 'hostescalation', 'hostextinfo',
                          'hostgroup', 'service', 'servicedependency',
                          'serviceescalation', 'serviceextinfo',
                          'servicegroup', 'timeperiod']

    conf_objs = [NagiosConf(url, res, opts.base_dir, opts.single_config, tag=opts.tag) for res in opts.resources]
    replacer = ConfReplacer(opts.base_dir, opts.initd, opts.bin, opts.print_changes)

    # Ensure this doesn't exist, so we don't get mixed configurations between different runs.
    if exists(replacer.tmp_dir):
        rmtree(replacer.tmp_dir)

    for conf in conf_objs:
        conf.write()
    if not opts.noop:
        replacer.push(noop=False)


if __name__ == "__main__":
    main()
