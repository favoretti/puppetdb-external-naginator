#!/usr/bin/env python

import sys
import os
import subprocess
import json
import hashlib
from optparse import OptionParser
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


class NagiosConf:

    def __init__(self, url, dtype):

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


def write_config(data, config="/etc/nagios3/naginator.cfg"):
    """ Write config to file and reload nagios. """
    if os.path.exists(config) and os.path.isfile(config):
        with open(config, 'r') as f:
            local_config = f.read()
        if (hashlib.md5(data).hexdigest() !=
           hashlib.md5(local_config).hexdigest()):
            os.rename(config, config + '.bak')
            with open(config, 'w') as f:
                f.write(data)
    else:
        with open(config, 'w') as f:
            f.write(data)


def reload_monitoring(service_bin="/usr/src/nagios3",
                      service_initd="/etc/init.d/nagios3",
                      service_config="/etc/nagios3/nagios.cfg"):
    """ Reload nagios if nagios config is sane. """

    sanity = subprocess.Popen([service_bin, "-v",
                               service_config],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    output, err = sanity.communicate()
    if sanity.poll() != 0:
        print """Sanity check of Nagios failed.
                  Not reloading.
                  Please fix the errors shown below:\r"""
        print output
        sys.exit(1)
    else:
        do_reload = subprocess.Popen([service_initd,
                                      "reload"], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        output, err = do_reload.communicate()
        if do_reload.poll() != 0:
            print "Reloading Nagios failed, please fix:\r"
            print output
            sys.exit(1)
        else:
            return True


def main():
    usage = '''usage: %prog [options] arg --hostname=host

    Resource types:

    command contact contactgroup host hostdependency hostescalation hostextinfo
    hostgroup service servicedependency serviceescalation serviceextinfo
    servicegroup timeperiod
'''
    parser = OptionParser(usage)
    parser.add_option("-i", "--hostname", dest="hostname",
                      help="Hostname or IP of PuppetDB host.")
    parser.add_option("--stdout", action="store_true", default=False,
                      help="Output configuration to stdout.")
    parser.add_option("-r", "--resources", dest="resources",
            help="""Comma-separated list of Nagios resources [default: all]""")
    parser.add_option("--reload", action="store_true", default=False,
                      help="Reload after config write.")
    parser.add_option("-b", "--bin", help="Location of monitoring binary",
                      action="store", type="string", dest="optbin")
    parser.add_option("-d", "--bininitd", help="Location of monitoring init.d",
                      action="store", type="string", dest="optinitd")
    parser.add_option("-c", "--conf", help="Location of monitoring config",
                      action="store", type="string", dest="conf")
    parser.add_option("-w", "--write", help="Location of config to write to",
                      action="store", type="string", dest="confwrite")

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


    conf_objs = [NagiosConf(url, res) for res in opts.resources]

    confs = [c.get() for c in conf_objs]
    if opts.stdout:
        print ''.join(confs)
    else:
        write_config(''.join(confs), opts.confwrite)
        if opts.reload:
            reload_monitoring(opts.optbin, opts.optinitd, opts.conf)


if __name__ == "__main__":
    main()
