from naginator import get_hosts_config
from mock import *


def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan",
            "title": "aaaa.ofi.lan",
            "parameters": {
                "address": "172.20.4.20",
                "alias": "aaaa.ofi",
                "contact_groups": "nobody",
                "host_name": "aaaa.ofi.lan",
                "use": "generic-host",
            },
        },
        {
            "certname": "bbbb.ofi.lan",
            "title": "bbbb.ofi.lan",
            "parameters": {
                "address": "172.20.4.30",
                "contact_groups": "nobody",
                "host_name": "bbbb.ofi.lan",
                "use": "generic-host",
                "alias": "bbbb.ofi",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_hosts_config():
    assert get_hosts_config() == """
define host {
        address                        172.20.4.20
        contact_groups                 nobody
        host_name                      aaaa.ofi
        use                            generic-host
        alias                          aaaa.ofi
}

define host {
        address                        172.20.4.30
        contact_groups                 nobody
        host_name                      bbbb.ofi
        use                            generic-host
        alias                          bbbb.ofi
}
"""

