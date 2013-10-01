from naginator import get_services_config
from mock import *

# {"certname":   "the certname of the associated host",
#  "resource":   "the resource's unique hash",
#  "type":       "File",
#  "title":      "/etc/hosts",
#  "exported":   "true",
#  "tags":       ["foo", "bar"],
#  "sourcefile": "/etc/puppet/manifests/site.pp",
#  "sourceline": "1",
#  "parameters": {<parameter>: <value>,
#                 <parameter>: <value>,
#                 ...}}
# mock = {}
# mock["default_templates"] = {
#     "command": {
#         "parameters": {
#             "command_name": "",
#             "command_line": "",
#         },
#     },
# }

def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "load_aaaa.ofi.lan" ,
            "parameters": {
                "check_command": "check_load!10,15,15!20,25,25",
                "max_check_attempts": "5",
                "normal_check_interval": "5",
                "host_name": "aaaa.ofi.lan",
                "notification_interval": "24x7",
                "notes_url": "http://url.here",
                "use": "generic",
                "service_description": "load",
                "retry_check_interval": "5",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "swap_bbbb.ofi.lan" ,
            "parameters": {
                "check_command": "check_swap!75!85",
                "max_check_attempts": "5",
                "normal_check_interval": "5",
                "host_name": "bbbb.ofi.lan",
                "notification_interval": "24x7",
                "notes_url": "http://url.here",
                "use": "generic",
                "service_description": "swap",
                "retry_check_interval": "5",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_services_config():
    assert get_services_config() == """
define service {
        check_command                  check_load!10,15,15!20,25,25
        max_check_attempts             5
        normal_check_interval          5
        host_name                      aaaa.ofi.lan
        notification_interval          24x7
        notes_url                      http://url.here
        use                            generic
        service_description            load
        retry_check_interval           5
}

define service {
        check_command                  check_swap!75!85
        max_check_attempts             5
        normal_check_interval          5
        host_name                      bbbb.ofi.lan
        notification_interval          24x7
        notes_url                      http://url.here
        use                            generic
        service_description            swap
        retry_check_interval           5
}
"""

