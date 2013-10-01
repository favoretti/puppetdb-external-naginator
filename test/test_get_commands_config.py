from naginator import get_commands_config
from mock import *



def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "command_check_load" ,
            "parameters": {
                "command_name": "check_load",
                "command_line": "$USER1$/check_snmp_load.pl -H $HOSTADDRESS$ -C soft_secure -w $ARG1$ -c $ARG2$ -T netsl -f",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "command_check_tcp" ,
            "parameters": {
                "command_name": "check_tcp",
                "command_line": "$USER1$/check_tcp -H $HOSTADDRESS$ -p $ARG1$ $ARG2$",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_commands_config():
    assert get_commands_config() == """
define command {
        command_name                   command_check_load
        command_line                   $USER1$/check_snmp_load.pl -H $HOSTADDRESS$ -C soft_secure -w $ARG1$ -c $ARG2$ -T netsl -f
}

define command {
        command_name                   command_check_tcp
        command_line                   $USER1$/check_tcp -H $HOSTADDRESS$ -p $ARG1$ $ARG2$
}
"""

