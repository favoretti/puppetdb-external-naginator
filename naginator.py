#!/usr/bin/env python

import sys
import os
import subprocess
import json
import hashlib
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

    def __init__(self, url, dtype, base_dir):

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


    def get_nagios_data(self, exported=True, tag=''):
        """ Function for fetching data from PuppetDB """
        if exported:
            if tag:
                query = """["and",
                    ["=", "exported",  true],
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", "tag", "{tag}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype,
                                                               tag=tag)
            else:
                query = """["and",
                    ["=", "exported",  true],
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype)
        else:
            if tag:
                query = """["and",
                    [ "not", ["=", ["parameter", "ensure"], "absent"]],
                    ["=", "type", "Nagios_{dtype}"],
                    ["=", "tag", "{tag}"],
                    ["=", ["node", "active"], true]]""".format(dtype=self.dtype,
                                                               tag=tag)
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
        conf_file = os.path.join(self.tmp_dir, '%s.cfg' % self.dtype)
        if not os.path.exists(self.tmp_dir):
            os.mkdir(self.tmp_dir)
        config = self.get()
        with open(conf_file, 'w') as f:
            f.write(config)




class ConfReplacer:

    def __init__(self, base_dir, initd, nagios_bin):
        self.base_dir = base_dir
        self.initd = initd
        self.bin = nagios_bin

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
        return changes != []


    def _is_valid(self):
        # [todo] Check there are no empty files.
        conf_file = join(self.base_dir, 'nagios.cfg')
        cmd = '%s -v %s > /dev/null 2>&1' % (self.bin, conf_file)
        return run(cmd) == 0


    def _replace(self):
        if exists(self.bak_dir):
            rmtree(self.bak_dir)

        move(self.dst_dir, self.bak_dir)
        move(self.tmp_dir, self.dst_dir)


    def _rollback(self):
        if exists(self.tmp_dir):
            rmtree(self.tmp_dir)
        move(self.dst_dir, self.tmp_dir)
        if exists(self.bak_dir):
            move(self.bak_dir, self.dst_dir)
        raise RuntimeError('Something is wrong in the generated configuration (look at tmp.d/)')


    def _reload(self):
        run('''%s reload > /dev/null 2>&1''' % self.initd)




def main():
    usage = '''Usage: %prog [options] arg

    Resource types:

    command contact contactgroup host hostdependency hostescalation hostextinfo
    hostgroup service servicedependency serviceescalation serviceextinfo
    servicegroup timeperiod
'''
    parser = OptionParser(usage)
    parser.add_option("-i", "--hostname", dest="hostname",
        help="Hostname or IP of PuppetDB host.")
    parser.add_option("-r", "--resources", dest="resources",
        help="""Comma-separated list of Nagios resources [default: all]""")
    parser.add_option("--base-dir", type="string", dest="base_dir", default="/etc/nagios",
        help="Base configuration directory [default: %default]")
    parser.add_option("-b", "--bin", type="string", dest="bin", default="/usr/bin/nagios",
        help="Nagios binary [default: %default]")
    parser.add_option("-d", "--initd", type="string", dest="initd", default='/etc/init.d/nagios',
        help="Nagios init.d script [default: %default]")
    parser.add_option("--reload", action="store_true", default=False,
        help="Reload after config write.")

    (opts, args) = parser.parse_args()

    all_resource_types = ['command', 'contact', 'contactgroup', 'host', 'hostdependency',
        'hostescalation', 'hostextinfo', 'hostgroup', 'service', 'servicedependency',
        'serviceescalation', 'serviceextinfo', 'servicegroup', 'timeperiod']

    if opts.hostname:
        url = "http://" + opts.hostname + ":8080/v3/resources"
    else:
        print "Please provide a hostname."
        sys.exit(1)

    if opts.resources:
        opts.resources = opts.resources.split(',')
    else:
        opts.resources = all_resource_types


    conf_objs = [NagiosConf(url, res, opts.base_dir) for res in opts.resources]
    replacer = ConfReplacer(opts.base_dir, opts.initd, opts.bin)

    # Ensure this doesn't exist, so we don't get mixed configurations between different runs.
    if exists(replacer.tmp_dir):
        rmtree(replacer.tmp_dir)

    for conf in conf_objs:
        conf.write()
    if opts.reload:
        replacer.push(noop=False)


if __name__ == "__main__":
    main()
