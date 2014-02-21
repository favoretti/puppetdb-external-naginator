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


# Some additional logic is required on the template to:
#  * Ignore Puppet parameters.
#  * Show as strings values that could be strings or could be lists.
TMPL = """{% set bad_params = ['notify', 'target', 'ensure', 'require', 'before', 'tag'] -%}
{% for element in elements %}
define {{ dtype }} {
{% for key, value in element['parameters']|dictsort -%}
  {%- if title_var -%}
   {{ title_var }}{{ element['title'] }}{{ "\n" }}
  {%- endif -%}
  {%- if key not in bad_params -%}
    {{ key.ljust(31)|indent(8,true) }}{{ value|join("") }}{{ "\n" }}
  {%- endif -%}
{% endfor -%}
}
{% endfor %}
"""


def get_nagios_data(dtype, exported=True, tag=''):
    """ Function for fetching data from PuppetDB """
    headers = {'Accept': 'application/json'}
    if exported:
        if tag:
            query = """["and",
                ["=", "exported",  true],
                [ "not", ["=", ["parameter", "ensure"], "absent"]],
                ["=", "type", "Nagios_{dtype}"],
                ["=", "tag", "{tag}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype,
                                                           tag=tag)
        else:
            query = """["and",
                ["=", "exported",  true],
                [ "not", ["=", ["parameter", "ensure"], "absent"]],
                ["=", "type", "Nagios_{dtype}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype)
    else:
        if tag:
            query = """["and",
                [ "not", ["=", ["parameter", "ensure"], "absent"]],
                ["=", "type", "Nagios_{dtype}"],
                ["=", "tag", "{tag}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype,
                                                           tag=tag)
        else:
            query = """["and",
                [ "not", ["=", ["parameter", "ensure"], "absent"]],
                ["=", "type", "Nagios_{dtype}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype)
    payload = {'query': query}
    r = requests.get(url, params=payload, headers=headers)
    ndata = json.loads(r.text)
    return ndata


def get_config(dtype, title_var):
    """Returns a python object with Nagios objects of type 'dtype'.

    dtype:  type of the Nagios objects to retrieve.
    """
    return jinja2.Template(TMPL).render(dtype=dtype,
                                        elements=get_nagios_data(dtype),
                                        title_var=title_var)


def get_all_config():
    """ This simply concatenates all data into one.

        Todo: Do this nice and neat as normal python
        people would..
    """
    return (get_config('command', 'command_name')
            + get_config('contact', 'contact_name')
            + get_config('contactgroup', 'contactgroup_name')
            + get_config('host', 'host_name')
            + get_config('hostdependency')
            + get_config('hostescalation')
            + get_config('hostextinfo', 'host_name')
            + get_config('hostgroup', 'hostgroup_name')
            + get_config('service')
            + get_config('servicedependency')
            + get_config('serviceescalation')
            + get_config('serviceextinfo')
            + get_config('servicegroup', 'servicegroup_name')
            + get_config('timeperiod', 'timeperiod_name'))


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


if __name__ == "__main__":
    usage = "usage: %prog [options] arg --hostname=host"
    parser = OptionParser(usage)
    parser.add_option("-i", "--hostname", dest="hostname",
                      help="Hostname or IP of PuppetDB host.")
    parser.add_option("--stdout", action="store_true", default=False,
                      help="Output configuration to stdout.")
    parser.add_option("-r", "--resource", dest="resource",
                      help="""Generate configuration for this Nagios resource.
    Options:
    command contact contactgroup host hostdependency hostescalation hostextinfo
    hostgroup service servicedependency serviceescalation serviceextinfo
    servicegroup timeperiod""")
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

    (options, args) = parser.parse_args()

    if options.hostname:
        url = "http://" + options.hostname + ":8080/resources"
    else:
        print "Please provide a hostname."
        sys.exit(1)

    if options.stdout:
        if options.resource:
            print get_config(options.resource)
        else:
            print get_all_config()
    else:
        write_config(get_all_config(), options.confwrite)
        if options.reload:
            reload_monitoring(options.optbin, options.optinitd, options.conf)
