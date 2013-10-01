from naginator import get_service_config
from mock import *


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
    assert get_service_config() == """
define service {
        check_command                  check_load!10,15,15!20,25,25
        host_name                      aaaa.ofi.lan
        max_check_attempts             5
        normal_check_interval          5
        notes_url                      http://url.here
        notification_interval          24x7
        retry_check_interval           5
        service_description            load
        use                            generic
}

define service {
        check_command                  check_swap!75!85
        host_name                      bbbb.ofi.lan
        max_check_attempts             5
        normal_check_interval          5
        notes_url                      http://url.here
        notification_interval          24x7
        retry_check_interval           5
        service_description            swap
        use                            generic
}

"""

