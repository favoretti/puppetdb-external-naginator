#!/usr/bin/env python

import sys
import os
import subprocess
import json
import hashlib
from string import Template
from optparse import OptionParser
import UserDict
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


TMPL = """
{% for element in elements %}define {{ dtype }} {
    {%- for key, value in element['parameters']|dictsort %}
        {{ key.ljust(31) }}{{ value }}
    {%- endfor %}
}

{% endfor %}
"""

service_defaults = {'max_check_attempts': 3,
                    'normal_check_interval': 5,
                    'notification_interval': 5,
                    'notes_url': 'http://ecgwiki.corp.ebay.com',
                    'retry_check_interval': 5}

hostextinfo_defaults = {'icon_image_alt': 'Solaris',
                        'statusmap_image': 'logos/solaris.gd2',
                        'icon_image': 'logos/solaris.png'}




def get_nagios_data(dtype, exported=True, tag=''):
    """ Function for fetching data from PuppetDB """
    headers = {'Accept': 'application/json'}
    if exported:
        if tag:
            query = """["and", ["=", "exported",  true],
                ["=", "type", "Nagios_{dtype}"],
                ["=", "tag", "{tag}"],
                ["=", ["node", "active"],
                true]]""".format(dtype=dtype, tag=tag)
        else:
            query = """["and", ["=", "exported",  true],
                ["=", "type", "Nagios_{dtype}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype)
    else:
        if tag:
            query = """["and", ["=", "type", "Nagios_{dtype}"],
                ["=", "tag", "{tag}"], ["=",
                ["node", "active"], true]]""".format(dtype=dtype, tag=tag)
        else:
            query = """["=", "type", "Nagios_{dtype}"],
                ["=", ["node", "active"], true]]""".format(dtype=dtype)
    payload = {'query': query}
    r = requests.get(url, params=payload, headers=headers)
    ndata = json.loads(r.text)
    return ndata



def get_config(dtype):
    """Returns a python object with Nagios objects of type 'dtype'.

    dtype:  type of the Nagios objects to retrieve.
    """
    elements = [ add_custom_parameters(dtype, elem) for elem in get_nagios_data(dtype) ]
    elements = [ add_default_parameters(dtype, elem) for elem in get_nagios_data(dtype) ]
    return jinja2.Template(TMPL).render(dtype=dtype, elements=elements)


def merge_dicts(values, defaults):
    """Given two dicts, use items in 'defaults' as default values for 'values'.
    """
    return dict( defaults.items() + values.items() )


def add_default_parameters(dtype, element):
    if dtype == 'host':
        element['parameters']['host_name'] = element['parameters']['alias']
    if dtype == 'contact':
        element['parameters']['contact_name'] = element['title']
    if dtype == 'contactgroup':
        element['parameters']['contactgroup_name'] = element['title']
    if dtype == 'command':
        element['parameters']['command_name'] = element['title']
    if dtype == 'hostextinfo':
        element['parameters']['host_name'] = element['certname']

    return element


def add_custom_parameters(dtype, element):
    # Insert default parameters, if needed.
    if dtype == 'hostextinfo':
        element['parameters'] = merge_dicts(element['parameters'], hostextinfo_defaults)
    if dtype == 'service':
        element['parameters'] = merge_dicts(element['parameters'], service_defaults)

    return element


def get_hosts_config():
    return get_config('host')

def get_contact_config():
    return get_config('contact')

def get_contactgroup_config():
    return get_config('contactgroup')

def get_command_config():
    return get_config('command')

def get_hostextinfo_config():
    return get_config('hostextinfo')

def get_service_config():
    return get_config('service')



def get_all_config():
    """ This simply concatenates all data into one.

        Todo: Do this nice and neat as normal python
        people would..
    """
    return (get_config('host') + get_config('hostextinfo') + get_config('contact')
            + get_config('contactgroup') + get_config('service') + get_config('command'))


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
            reload_nagios()
    else:
        with open(config, 'w') as f:
            f.write(data)
        reload_nagios()


def reload_nagios():
    """ Reload nagios if nagios config is sane. """
    sanity = subprocess.Popen(["/usr/sbin/nagios3", "-v",
                               "/etc/nagios3/nagios.cfg"],
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
        do_reload = subprocess.Popen(["/etc/init.d/nagios3",
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

    (options, args) = parser.parse_args()

    if options.hostname:
        url = "http://" + options.hostname + ":8080/resources"
    else:
        print "Please provide a hostname."
        sys.exit(1)

    if options.stdout:
        print get_all_config()
    else:
        write_config(get_all_config())
