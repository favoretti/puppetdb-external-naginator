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


class Chainmap(UserDict.DictMixin):
    """Combine multiple mappings for sequential lookup.

    For example, to emulate Python's normal lookup sequence:

        import __builtin__
        pylookup = Chainmap(locals(), globals(), vars(__builtin__))
    """

    def __init__(self, *maps):
        self._maps = maps

    def __getitem__(self, key):
        for mapping in self._maps:
            try:
                return mapping[key]
            except KeyError:
                pass
        raise KeyError(key)

service_template = """
define service {
        check_command                  ${check_command}
        max_check_attempts             ${max_check_attempts}
        normal_check_interval          ${normal_check_interval}
        host_name                      ${host_name}
        notification_interval          ${notification_interval}
        notes_url                      ${notes_url}
        use                            ${use}
        service_description            ${service_description}
        retry_check_interval           ${retry_check_interval}
}
"""

command_template = """
define command {
        command_name                   ${command_name}
        command_line                   ${command_line}
}
"""

host_template = """
define host {
        address                        ${address}
        contact_groups                 ${contact_groups}
        host_name                      ${alias}
        use                            ${use}
        alias                          ${alias}
}
"""

contact_template = """
define contact {
        contact_name                   ${contact_name}
        use                            ${use}
        alias                          ${alias}
        email                          ${email}
}
"""

contactgroup_template = """
define contactgroup {
        contactgroup_name              ${contactgroup_name}
        members                        ${members}
        alias                          ${alias}
}
"""

hostextinfo_template = """
define hostextinfo {
        host_name                      ${host_name}
        icon_image_alt                 ${icon_image_alt}
        statusmap_image                ${statusmap_image}
        icon_image                     ${icon_image}
}
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


def get_hosts_config():
    """ To fetch and parse hosts configuration.

        Todo: Merge into one method.."""
    hosts_config = ''
    hosts = get_nagios_data('host')
    for host in hosts:
        s = Template(host_template)
        hosts_config += s.safe_substitute(host['parameters'])
    return hosts_config


def get_hostextinfo_config():
    """ To fetch and parse hostextinfo configuration.

        Todo: Merge into one method.."""
    hostextinfos = get_nagios_data('hostextinfo')
    hostextinfo_config = ''
    for hostextinfo in hostextinfos:
        s = Template(hostextinfo_template)
        hostextinfo['parameters']['host_name'] = hostextinfo['certname']
        param_prefill = Chainmap(hostextinfo['parameters'],
                                 hostextinfo_defaults)
        hostextinfo_config += s.safe_substitute(param_prefill)
    return hostextinfo_config


def get_contacts_config():
    """ To fetch and parse contacts configuration.

        Todo: Merge into one method.."""
    contacts = get_nagios_data('contact')
    contacts_config = ''
    for contact in contacts:
        s = Template(contact_template)
        contact['parameters']['contact_name'] = contact['title']
        contacts_config += s.safe_substitute(contact['parameters'])
    return contacts_config


def get_contactgroups_config():
    """ To fetch and parse contactgroups configuration.

        Todo: Merge into one method.."""
    contactgroups = get_nagios_data('contactgroup')
    contactgroups_config = ''
    for contactgroup in contactgroups:
        s = Template(contactgroup_template)
        contactgroup['parameters']['contactgroup_name'] = contactgroup['title']
        contactgroups_config += s.safe_substitute(contactgroup['parameters'])
    return contactgroups_config


def get_services_config():
    """ To fetch and parse services configuration.

        Todo: Merge into one method.."""
    services = get_nagios_data('service')
    services_config = ''
    for service in services:
        s = Template(service_template)
        param_prefill = Chainmap(service['parameters'], service_defaults)
        services_config += s.safe_substitute(param_prefill)
    return services_config


def get_commands_config():
    """ To fetch and parse commands configuration.

        Todo: Merge into one method.."""
    commands = get_nagios_data('command')
    commands_config = ''
    for command in commands:
        command['parameters']['command_name'] = command['title']
        s = Template(command_template)
        commands_config += s.safe_substitute(command['parameters'])
    return commands_config


def get_config():
    """ This simply concatenates all data into one.

        Todo: Do this nice and neat as normal python
        people would..
    """
    config = (get_hosts_config() + get_hostextinfo_config()
              + get_contacts_config() + get_contactgroups_config()
              + get_services_config() + get_commands_config())
    return config


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

usage = "usage: %prog [options] arg --hostname=host"
parser = OptionParser(usage)
parser.add_option("-i", "--hostname", dest="hostname",
                  help="Hostname or IP of PuppetDB host.")
(options, args) = parser.parse_args()

if __name__ == "__main__":
    if options.hostname:
        url = "http://" + options.hostname + ":8080/resources"
        write_config(get_config())
    else:
        print "Please provide a hostname."
        sys.exit(1)
