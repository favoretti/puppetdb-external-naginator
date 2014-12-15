#!/usr/bin/env python
"""
This script is meant to replace the standard nagios 'notify-service-by-mail' command (usually implemented as a
commandline in the nagios config file). The script will send out a fairly standard mail like nagios usually does, but
will add graphics as MIME attachments to the mail when the service is configured with extra custom attributes in Nagios.
Extra attributes will be picked up automatically since nagios will put them in Environment Variables.

commandline options for this script:
--imgDirectory  : directory containing images OK.png, WARNING.png CRITICAL.png UNKNOWN.png
--bgcolor       : backgroundcolor for first html table line in mail (eg: #F2B479)
--fgcolor       : foregroundcolor for companyname in first html table line
--name          : Company name in first html table line
--logFile       : location of logfile
--debuglevel    : loglevel
--mailsender    : From-address for mail
--timeout       : timeout (in seconds) for retrieving remote data
--configfile    : configfile to put options in
--subjectPrefix : prefix for mail subject

recognized custom attributes for nagios services:
  _GRAPHURLn : one or more URLs that return an image directly (of type .png)
  _DASHURLn  : one or more URLs to a webpage where the first displayed image will be taken. When the URL contains an
               anchor ('#'), the first image after that anchor is taken

Note: since Nagios cannot escape the ampersand character ('&'), replace it with '__AMPERSAND__' in your config.

example:
define service{
  use                   service-defaults
  host_name	            myhost.example.com
  service_description	Check the XYZ service
  check_command	        check_xyz
  _GRAPHURL1            "http://graphite.example.com/render?graph=example1__AMPERSAND__period=lastday"
  _GRAPHURL2            "http://graphite.example.com/render?graph=example2__AMPERSAND__period=lastday"
  _DASHURL1             "http://dash.example.com/overview_page/#graph5"
}

example command configuration:
define command{
    command_name    notify-svcgraph-by-email
    command_line    /usr/local/bin/nagiosmailer.py --subjectPrefix '[ my Nagios environment ]'
}

Author: Reinoud van Leeuwen <rvanleeuwen@ebay.com>
Date:   april 2013
"""

# TODO: make script usable for hostmails too (and edit commandlinedescription when this is done)

import argparse
import socket
import logging
import logging.handlers
import os
import re
import requests
import smtplib
import urllib2

from ConfigParser import ConfigParser, ParsingError
from BeautifulSoup import *
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

__author__ = "Reinoud van Leeuwen"
__version__ = "1.0.0"
__date__ = "04-29-2013"
__maintainer__ = "SiteOps eBay Classifieds"
__email__ = "siteops@marktplaats.nl"
__status__ = "Production"

# Display these fields in bold in HTML
BOLDVARS = ['Host', 'Service']


def sendGraphEmail(logger, graph_urls, subject, sender, receiver, textBody, htmlBody, headers, imgDirectory, timeout):
    """Builds and sends an email with inline graph(s), and provide plaintext alternative.

    :param logger: logobject
    :type logger: logging.getlogger
    :param graph_urls: list of URLS with images to retrieve. Note '__AMPERSAND__' in the URL will be replaced by '&'
    :type graph_urls: list
    :param subject: Email subject line
    :type subject: string
    :param sender: an email address
    :type sender: string
    :param receiver: single email addresses to send to.
    :type receiver: string
    :param textBody: text alternative body
    :type textBody: string
    :param htmlBody: html alternavive body
    :type htmlBody: string
    :param headers: extra headers to add to mail
    :type headers: dict
    :param imgDirectory: local directory where images are stored
    :type imgDirectory: string
    :param timeout: timeout (in seconds) for retrieving remote content
    :type timeout: int
    :returns: None
    """

    logger.debug("start composing mail")
    msg = MIMEMultipart()
    msg['To'] = receiver
    msg['From'] = sender
    msg['Subject'] = subject
    msg.add_header('To:', sender)
    msg.preamble = 'This is a multi-part message in MIME format.'
    for header, value in headers.iteritems():
        msg.add_header(header, value)
        logger.debug("added header %s" % header)

    msgAlternative = MIMEMultipart('alternative')
    msgAlternative.attach(MIMEText(textBody, 'plain'))

    # html part and images need to be in a 'related' Mime container
    related = MIMEMultipart('related')
    related.attach(MIMEText(htmlBody, 'html'))

    msgAlternative.attach(related)

    msg.attach(msgAlternative)

    stateImage = getSingleEnvVar('NAGIOS_SERVICESTATE') + '.png'
    try:
        filename = imgDirectory + '/' + stateImage
        msgImage = MIMEImage(open(filename, 'rb').read())
        msgImage.add_header('Content-ID', '<%s@%s>' % (stateImage, socket.getfqdn()))
        msgImage.add_header('Content-Disposition', 'inline', filename=stateImage)
        related.attach(msgImage)
        logger.debug("succesfully added image %s" % stateImage)
    except Exception as inst:
        logger.warning("error adding image %s: %s" % (stateImage, inst))

    for num, graph_url in enumerate(graph_urls):
        graph_url = graph_url.replace('__AMPERSAND__', '&')
        logger.debug("graphurl to fetch is: %s", graph_url)

        try:
            graph = requests.get(graph_url, timeout=timeout)
            kind, imgtype = graph.headers['content-type'].split('/')
            logger.debug("successfully retrieved %s of type %s" % (kind, imgtype))
        except requests.exceptions.Timeout as inst:
            logger.warning("did not receive %s in time: %s" % (graph_url, inst))
            kind = ''
        except Exception as inst:
            logger.warning("did not receive %s for reason: %s" % (graph_url, inst))
            kind = ''

        if kind != 'image':
            logger.warning("URL %s returns no image but %s" % (graph_url, kind))
        else:
            imgpart = MIMEImage(graph.content, _subtype=imgtype)
            imgpart.add_header('Content-Disposition', 'attachment', filename="graph%s" % num)
            imgpart.add_header('Content-ID', '<graph%s>' % num)
            related.attach(imgpart)
            logger.debug("attached image %s to mail" % graph_url)

    if 'Message-ID' in headers:
        msgidstr = ", MessageID: '%s'" % headers['Message-ID']
    else:
        msgidstr = ""

    s = smtplib.SMTP()
    try:
        s.connect()
        s.sendmail(sender, receiver, msg.as_string())
        s.close()
        logger.info("sent mail OK. Subject: '%s' %s" % (subject, msgidstr))
    except Exception as out:
        logger.error("Sending mail failed: %s" % out)


def parseWebpage(logger, urls, timeout):
    """Parse the webpages in the list of urls and return the first 'img src' URL in each page as a list

    Note: when the URL contains an anchor ('#'), return the first img src after that anchor

    In the future we might want to extend this function with some (short timed) caching for urllib2

    :param logger: logobject
    :type logger: logging.getlogger()
    :param urls: a list of URLS of webpages to parse
    :type urls: list
    :returns a list of URLs to images to retrieve
    :rtype: list
    """
    returnList = []
    logger.debug("parsewebpage with urls: %s" % repr(urls))
    for fullUrl in urls:
        logger.debug("trying to parse url %s" % fullUrl)
        try:
            baseUrl, anchor = fullUrl.split('#')
        except ValueError:
            baseUrl = fullUrl
            anchor = None
        logger.debug("baseurl = %s" % baseUrl)
        logger.debug("anchor  = %s" % anchor)
        try:
            page = urllib2.urlopen(baseUrl, None, timeout=timeout).read()
        except Exception as inst:
            page = None
            logger.warning("could not retrieve URL %s: %s" % (baseUrl, repr(inst)))
        soup = BeautifulSoup(page)
        if page:
            if anchor is None:
                link = soup.find('html').img['src']
                logger.debug("no anchor found, link is %s" % link)
            else:
                link = soup.find('a', {"name": anchor}).img['src']
                logger.debug("anchor found, link is %s" % link)
        else:
            link = None

        if link:
            returnList.append(link)

    return returnList


def getMultipleEnvVars(startswith=''):
    """return a dict of environment variables starting with a string

    :param startswith: a string to match to the start of environment variables to fetch
    :type startswith: string
    :returns a dict with names and values of found environment variables
    :rtype: dict
    """
    return dict((k, v) for k, v in os.environ.iteritems() if k.startswith(startswith))


def getSingleEnvVar(varName):
    """lookup a single environment variable or return empty string when not found

    :param varName: name of environment variable to look up
    :type varName: string
    :returns value of the variable or empty string when variable is not set
    :rtype: string
    """
    # noinspection PyBroadException
    try:
        return os.environ[varName]
    except:
        return ''


def mailTextBody(nagiosMappings):
    """create a fairly standard Nagios mail TextBody. Graphs will be added later

    :param nagiosMappings: dict of displaystrings and associated Nagios environment variables
    :type nagiosMappings: dict
    :returns: string for textbody of mail
    :rtype: string
    """
    body = "***** [%s] Nagios *****\n\n" % socket.getfqdn()
    for displayString, envVar in nagiosMappings.iteritems():
        body += "%s: %s\n" % (displayString, getSingleEnvVar(envVar))
    body += "\nAdditional Info:\n\n%s\n" % getSingleEnvVar('NAGIOS_SERVICEOUTPUT')
    return body


def mailHtmlBody(logger, graphUrls, companyBgColor, companyFgcolor, companyName, nagiosMappings):
    """create a html mailbody.

    :param graphUrls: URL's that will be displayed in the mail
    :type graphUrls: list
    :param companyBgColor: html backgroundcolor for the first table row. Should be a hex color ('#123456')
    :type companyBgColor: string
    :param nagiosMappings: dict of displaystrings and associated Nagios environment variables
    :type nagiosMappings: dict
    :returns: a string with html textbody for mail
    :rtype: string
    """
    body = '<html><body><table width="100%" border="0" cellspacing="0">\n'
    body += '<tr><td bgcolor="%s">\n' % companyBgColor
    body += '  <img src="cid:%s.png@%s" align="left">\n' % (getSingleEnvVar('NAGIOS_SERVICESTATE'), socket.getfqdn())
    body += '</td>'
    body += '<td bgcolor="%s" align="right">\n' % companyBgColor
    body += '<font color="%s"><b>%s&nbsp;</b></font>' % (companyFgcolor, companyName)
    body += '</td></tr>\n'
    body += '<tr>\n'
    body += '<td colspan="2" align="center">**** [%s] Nagios</td>\n' % socket.getfqdn()
    body += '</tr>\n'
    for displayString, envVar in nagiosMappings.iteritems():
        displayVar = getSingleEnvVar(envVar)
        if displayString in BOLDVARS:
            displayVar = '<b>%s</b>' % displayVar
        body += '<tr><td>%s: </td><td align="left">%s</td></tr>\n' % (displayString, displayVar)
    body += '<tr><td>Additional info: </td><td>&nbsp;</td></tr>\n'
    body += '<tr><td colspan="2">%s</td></tr>\n' % getSingleEnvVar('NAGIOS_SERVICEOUTPUT')
    for num, graph_url in enumerate(graphUrls):
        try:
            title = re.search('\?title=(.*?)(&|__AMPERSAND__)', graph_url).group(1).replace('+', ' ')
        except:
            title = ""
        body += '<tr><td colspan="2" align="left">Graph %s:</td></tr>\n' % title
        body += '<tr><td colspan="2" align="left"><img src="cid:graph%s"></td></tr>\n' % num
    body += '</table></body></html>\n'
    logger.debug("--- start of html mailbody ---")
    logger.debug(body)
    logger.debug("--- end of html mailbody ---")
    return body


def mailSubject(logger, prefix=None):
    """create the standard nagios subject line for mails, and add the optional prefix

    :param prefix: prefix to add to start of subjectline
    :type prefix: string
    :returns a string to use as subject for the mail
    :rtype: string
    """
    subject = "%s: %s : %s **" % (getSingleEnvVar('NAGIOS_SERVICESTATE'),
                                  getSingleEnvVar('NAGIOS_HOSTDISPLAYNAME'),
                                  getSingleEnvVar('NAGIOS_SERVICEDISPLAYNAME'))
    if prefix is not None:
        subject = "%s %s" % (prefix, subject)
    logger.debug("mailsubject: %s" % subject)
    return subject


def mailHeaders(logger, replyto):
    """generate some extra headers to assist smart mailreaders in threading

    the following nagios macros are used:
    $SERVICEEVENTID$       A globally unique number associated with the service's current state. Every time a a service
                           (or host) experiences a state change, a global event ID number is incremented by one (1).
                           If a service has experienced no state changes, this macro will be set to zero (0).
    $LASTSERVICEEVENTID$   The previous (globally unique) event number that given to the service.

    :param logger: logging object
    :type logger: logging.getlogger()
    :returns: a dict of headernames (keys) and their values
    :rtype: dict
    """
    msgid = getSingleEnvVar('NAGIOS_SERVICEEVENTID')
    refid = getSingleEnvVar('NAGIOS_LASTSERVICEEVENTID')
    hostname = socket.getfqdn()
    headers = {'X-nagiosserver': hostname,
               'reply-to': replyto}
    if id and refid:
        headers['Message-ID'] = "<nagiosid-%s@%s>" % (msgid, hostname)
        headers['References'] = "<nagiosid-%s@%s>" % (refid, hostname)
    for header, value in headers.iteritems():
        logger.debug("header %s : %s" % (header, value))
    return headers


def do_options(configDefaults):
    """parse commandline options and get defaults from configfile

    :return: options object
    :rtype: argparse.Namespace
    """
    description = "an extended mailer for nagios than can add images to servicenotification mails"
    parser = argparse.ArgumentParser(description=description)
    for key in configDefaults.keys():
        parser.add_argument("-%s" % key[0], "--%s" % key,
                            help="%s (default: '%s')" % (configDefaults[key]['help'], configDefaults[key]['default']),
                            choices=configDefaults[key]['choices'])
    options = parser.parse_args()
    return options


def getConfig(configfile, configDefaults, logBacklog):
    """Read configfile and take defaults for values not supplied

    :param configfile: file to read
    :type configfile: string
    :param logBacklog: lines that should be logged later
    :type logBacklog: list
    :returns dict with values, either from config file or from defaults, and logBacklog
    :rtype: dict, list
    """
    configDict = {}
    config = ConfigParser()
    if os.path.exists(configfile):
        logBacklog.append(("DEBUG", "reading from configfile %s" % configfile))
        try:
            fp = open(configfile)
            config.readfp(fp)
            fp.close()
        except ParsingError as error:
            logBacklog.append(("INFO", "Error parsing configfile %s: %s" % (configfile, error)))
            return configDefaults, logBacklog
    else:
        logBacklog.append(("DEBUG", "configfile %s not found, using defaults and cmdlineoptions" % configfile))

    try:
        dummy = config.get('Main', 'test')
    except:
        try:
            config.add_section('Main')
        except:
            pass

    for key in configDefaults.keys():
        try:
            configDict[key] = config.get('Main', key)
            logBacklog.append(("DEBUG", "using %s '%s' from configfile" % (key, configDict[key])))
        except:
            pass

    return configDict, logBacklog


def setLogger(options, logBacklog):
    """set up a logfile

    :param options: parsed options
    """
    logger = logging.getLogger('main')
    loglevel = logging.getLevelName(options.debuglevel)
    logger.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')

    # try until a working logging path is found
    for logpath in [options.logFile,
                    '/var/log/nagios3/nagiosmailer.log',
                    '/tmp/nagiosmailer.log', ]:
        try:
            file_logger = logging.handlers.RotatingFileHandler(logpath, maxBytes=100000, backupCount=5)
            file_logger.setLevel(loglevel)
            file_logger.setFormatter(formatter)
            logger.addHandler(file_logger)

            logBacklog.append(("DEBUG", "using %s for logging" % logpath))
            break
        except Exception as inst:
            logBacklog.append(("DEBUG", "not using %s for logpath (%s)" % (logpath, inst)))

    # log the things we couldn't log until now
    for (lvl, line) in logBacklog:
        logger.log(logging.getLevelName(lvl), line)

    return logger


def main():
    nagiosDict = {'Notification Type': 'NAGIOS_NOTIFICATIONTYPE',
                      'Service': 'NAGIOS_SERVICEDISPLAYNAME',
                      'Host': 'NAGIOS_HOSTDISPLAYNAME',
                      'Address': 'NAGIOS_HOSTADDRESS',
                      'State': 'NAGIOS_SERVICESTATE',
                      'Docs': 'NAGIOS_SERVICENOTESURL',
                      'Date/Time': 'NAGIOS_LONGDATETIME'}

    configDefaults = {'imgDirectory': {'default': '/etc/nagiosmailer/',
                                       'help': 'directory containing images OK.png, WARNING.png CRITICAL.png UNKNOWN.png',
                                       'choices': None},
                      'bgcolor': {'default': '#F2B479',
                                  'help': 'backgroundcolor for first html table line in mail (eg: #F2B479)',
                                  'choices': None},
                      'fgcolor': {'default': '#21479C',
                                  'help': 'foregroundcolor for companyname in first html table line',
                                  'choices': None},
                      'name': {'default': 'Acme Corp',
                               'help': 'Company name in first html table line',
                               'choices': None},
                      'logFile': {'default': '/var/log/nagios3/nagiosmailer.log',
                                  'help': 'location of logfile',
                                  'choices': None},
                      'debuglevel': {'default': 'INFO',
                                     'help': 'loglevel',
                                     'choices': ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']},
                      'mailsender': {'default': 'nagios@%s' % socket.getfqdn(),
                                      'help': 'From-address for mail',
                                      'choices': None},
                      'timeout': {'default': 1,
                                  'help': 'timeout (in seconds) for retrieving remote data',
                                  'choices': None},
                      'configfile': {'default': '/etc/nagiosmailer/nagiosmailer.conf',
                                     'help': 'configfile to put options in',
                                     'choices': None},
                      'subjectPrefix': {'default': '',
                                        'help': 'prefix for mail subject',
                                        'choices': None}}

    # remember things to log before we know where to log
    logBacklog = []

    # parse commandline options first; so we can use an alternative config file
    options = do_options(configDefaults)
    configfile = options.configfile or configDefaults['configfile']['default']
    config, logBacklog = getConfig(configfile, configDefaults, logBacklog)
    #merge configfile options in commandline options.

    for key in configDefaults.keys():
        options.__dict__[key] = options.__dict__.get(key) or config.get(key) or configDefaults[key]['default']

    logger = setLogger(options, logBacklog)

    for option in options.__dict__:
        logger.debug("option %s is '%s'" % (option, options.__dict__[option]))


    directUrls = getMultipleEnvVars('NAGIOS__SERVICEGRAPHURL').values()
    logger.debug("found direct URLS:")
    for url in directUrls:
        logger.debug("  - %s" % url)

    inDirectUrls = parseWebpage(logger, getMultipleEnvVars('NAGIOS__SERVICEDASHURL').values(), options.timeout)
    logger.debug("found indirect URLS:")
    for url in inDirectUrls:
        logger.debug("  - %s" % url)

    graphUrls = directUrls + inDirectUrls
    textBody = mailTextBody(nagiosDict)
    htmlBody = mailHtmlBody(logger, graphUrls, options.bgcolor, options.fgcolor, options.name, nagiosDict)
    subject = mailSubject(logger, options.subjectPrefix)
    receiver = getSingleEnvVar('NAGIOS_CONTACTEMAIL')
    replyto = receiver
    logger.debug("mailreceiver: %s" % receiver)

    headers = mailHeaders(logger, replyto)

    if receiver:
        sendGraphEmail(logger,
                       graphUrls,
                       subject,
                       options.mailsender,
                       receiver,
                       textBody,
                       htmlBody,
                       headers,
                       options.imgDirectory,
                       options.timeout)
    else:
        logger.warning("no receiver found, not sending mail")

if __name__ == '__main__':
    main()
