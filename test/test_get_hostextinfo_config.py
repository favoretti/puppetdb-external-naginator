from naginator import get_config
from mock import *

def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "aaaa.ofi.lan" ,
            "parameters": {
                "icon_image_alt": "alt text for aaaa",
                "statusmap_image": "some statusmap for aaaa",
                "icon_image": "some icon for aaaa",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "bbbb.ofi.lan" ,
            "parameters": {
                "icon_image_alt": "alt text for bbbb",
                "statusmap_image": "some statusmap for bbbb",
                "icon_image": "some icon for bbbb",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_hostextinfo_config():
    assert get_config('hostextinfo') == """
define hostextinfo {
        host_name                      aaaa.ofi.lan
        icon_image                     some icon for aaaa
        icon_image_alt                 alt text for aaaa
        statusmap_image                some statusmap for aaaa
}

define hostextinfo {
        host_name                      bbbb.ofi.lan
        icon_image                     some icon for bbbb
        icon_image_alt                 alt text for bbbb
        statusmap_image                some statusmap for bbbb
}

"""

