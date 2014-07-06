# Naginator.py

Pull Nagios exported resources from PUppetDB REST API and generate Nagios configurations based on that

Very simple, published on request from a PuppetCamp presentation. If you do extend it, do share back please ;)


## Custom attributes


Naginator can generate custom attributes in Nagios configurations. These can be used by a custom mailer to include -for
 instance- graphs in the alert mails.


### Exporting

First step is to export the custom attributes to the puppetdb.

Make a define somewhere which does absolutely nothing:

```puppet
define nagios::nagios_extended_attribute( $content) {
}
```

Now in your manifest you probably already have some nagios exports like this:

```puppet
@@nagios_service {'check_load_myserver.example.com':
  ensure       => present,
  command_line => 'some_command';
}
```

To add custom variables to this, use your new define like this:

```puppet
@@nagios::nagios_extended_attribute {'check_load_myserver.example.com':
  content => { '_GRAPHURL1' => 'http://mymuninserver.example.com/munin/munin/myserver.example.com/load-day.png'},
  tag     => ['Nagios_custom_service_attribute'];
}
```

A few important points here:

- give it the same name as the exported nagios command
- the content parameter is a *hash*. It can contain multiple keys and values
- keys in the content hash should start with an underscore (that is how nagios supports custom attributes)
- use a tag in the form 'Nagios_custom_${nagiostype}_attribute


### Generating

Use the option --custom_attributes when running naginator.py. This will result in a service definition like:

```
define service {
        check_command                  check_nrpe_1arg!check_load
        host_name                      myserver.example.com
        max_check_attempts             3
        normal_check_interval          5
        notification_interval          15
        retry_check_interval           5
        service_description            check_load
        use                            puppet-generic-service
        _GRAPHURL1                     http://mymuninserver.example.com/munin/munin/myserver.example.com/load-day.png
}
```

### using

When you use a custom mail script for alerting, the custom attribute is (like all attributes) exported as an environment
variable so it can be used to grab the image from a graphing server and include it in the sent mail.

# nagiosmailer.py

Nagiosmailer is a script to use instead of the 'echo CRITITAL | mail'-construct that is default in most Nagios setups.
Using nagiosmailer has a few advantages over the standard mails:

 - html mails (with text alternative)
 - threading in mails so 'OK' will end up in the same mailthread as the 'CRITICAL' mail
 - the possibility to include graphs from munin, graphite or another graphing solution, as long as the images are 
   available to fetch indivudually from the nagios server without password. (you will need to run naginator with
   --custom_attributes for this)
   
Currently nagiosmailer only support service emails, not host emails.
   
## prerequisites

 - naginator for nagios config generation
 - python module BeautifulSoup installed
 - icon files OK.png, WARNING.png, UNKNOWN.png CRITICAL.png in /etc/nagiosmailer
 - a commands.cfg file in nagios that has the nagiosmailer enables for service mails:
 ...
 define command{
    command_name    notify-service-by-email
    command_line    /usr/local/bin/nagiosmailer.py 
 }
 ...
 - /var/log/nagios3/ writable by the user nagios is running under
 - _GRAPHURLn custom attributes for services that refer to an absolute URL that displays a meaningfull graph about the
   service (e.g. http://mymuninserver.example.com/munin/munin/myserver.example.com/load-day.png)
 _ _DASHURLn attributes that refer to an anchor on a webpage, after which the first graph is taken
   (e.g. http://mygraphitedashboard.example.com/dashboard/webserveroverview#averageload )
 - make sure that the graphs can be retrieved from the nagios server without authentication
 
 ## example
 
 You can now send mails like this from nagios:
 
 ![Example HTML mail](/screenshots/examplemail.png?raw=true "Example HTML mail")
 
 The HTML is easily changeable in the python source