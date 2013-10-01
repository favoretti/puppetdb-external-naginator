from naginator import get_contactgroup_config
from mock import *

def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "admins" ,
            "parameters": {
                "contactgroup_name": "admins",
                "members": "alfred,bob",
                "alias": "Administrators",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "visitors" ,
            "parameters": {
                "contactgroup_name": "visitors",
                "members": "carl,danny",
                "alias": "Visitors",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_contactgroups_config():
    assert get_contactgroup_config() == """
define contactgroup {
        alias                          Administrators
        contactgroup_name              admins
        members                        alfred,bob
}

define contactgroup {
        alias                          Visitors
        contactgroup_name              visitors
        members                        carl,danny
}

"""

