# -*- coding: utf-8 -*-
"""
CLI Tool for Paessler's PRTG (http://www.paessler.com/)
"""

import argparse
import os
import logging
import yaml

from prtg.client import Client
from prtg.models import LIST_TYPE_PROPS, NameMatch, Query, RuleChain
from prettytable import PrettyTable


__ARG_DEFAULT_LOGGING_LEVEL = 'WARN'
__ENV_VARNAME_ENDPOINT = 'PRTGENDPOINT'
__ENV_VARNAME_USERNAME = 'PRTGUSERNAME'
__ENV_VARNAME_PASSWORD = 'PRTGPASSWORD'


def load_environment():
    """
    Load config from environment variables.
    :var PRTGENDPOINT: Environment variable indicating PRTG endpoint. Default: 'http://127.0.0.1:8080'.
    :var PRTGUSERNAME: Environment variable indicating PRTG username. Default: 'prtgadmin'.
    :var PRTGPASSWORD: Environment variable indicating PRTG password. Default: 'prtgadmin'.
    :return: Endpoint, username and password.
    """
    endpoint = os.getenv(__ENV_VARNAME_ENDPOINT, 'http://127.0.0.1:8080')
    username = os.getenv(__ENV_VARNAME_USERNAME, 'prtgadmin')
    password = os.getenv(__ENV_VARNAME_PASSWORD, 'prtgadmin')
    return endpoint, username, password


def load_rules(rule_path):
    """
    Load rules from file.
    :param rule_path: Rules YAML fully-qualified filename.
    :return: Rules object resulting from YAML parsing.
    """
    return yaml.load(open(rule_path).read())['rules']


class CliResponse(object):
    """
    PRTG client response object. To be used once per command.
    """

    def __init__(self, response, mode='pretty', sort_by=None):
        """
        :param response: Response object (as in the response coming out of the Client instance).
        :param mode: Print (data presentation) mode: 'csv' or 'pretty'.
        :param sort_by: Sorting column name (e.g.: 'objid').
        """
        self.mode = mode
        self.sort_by = sort_by
        self.response = response

        columns = set()

        for item in self.response:
            for key, value in item.__dict__.items():
                columns.add(key)
                if isinstance(value, list):
                    item.__setattr__(key, ' '.join(value))
                if isinstance(value, int):
                    item.__setattr__(key, str(value))

        self.columns = list(columns)
        # TODO: Better filtering
        self.columns = [x for x in self.columns if not any([x == 'active', x == 'type'])]
        self.columns.sort()

    def _csv(self):
        """
        Convert retrieved data to CSV.
        :return: String with the CSV representation of the data.
        """
        out = ','.join(self.columns) + '\n'
        _lst = list()

        for resp in self.response:
            try:
                _lst.append(','.join([resp.__getattribute__(x) for x in self.columns]))
            except AttributeError or TypeError:
                pass
        _lst.sort()

        return out + '\n'.join(_lst)

    def _pretty(self):
        """
        Prettify retrieved data, making it fit in an ASCII table.
        :return: String with the ASCII table.
        """
        p = PrettyTable(self.columns)

        for resp in self.response:
            try:
                p.add_row([resp.__getattribute__(x) for x in self.columns])
            except AttributeError or TypeError:
                pass

        return p.get_string(sortby=self.sort_by)

    def __str__(self):
        if self.mode == 'pretty':
            return self._pretty()
        if self.mode == 'csv':
            return self._csv()


def _get_parent(client, entity):
    parent = None
    if hasattr(entity, 'parentid') and entity.parentid:
        logging.debug('PARENTID: {}'.format(entity.parentid))
        try:
            parent = client.cache.get_object(entity.parentid)
        except KeyError:
            pass
    logging.debug('PARENT: {}'.format(parent))
    return parent


def apply_rules(client, rules, content_type):
    """
    Apply property change rules.
    :param client: PRTG Client instance.
    :param rules: Rule dictionaries list.
    :param content_type: Content type, i.e., one of {groups, devices, sensors}.
    """

    rule_chain = RuleChain(*rules)

    change_map = {}
    for entity in client.cache.get_content(content_type):
        change_map[entity.objid] = rule_chain.apply(entity, _get_parent(client, entity))

    for objid, changes in change_map.items():
        for prop, new_value in changes.items():
            query = Query(
                client, target='setobjectproperty', objid=objid, name=prop, value=new_value
            )
            client.query(query)


def get_args():
    """
    Get command-line arguments.
    :return: Arguments object.
    """
    endpoint, username, password = load_environment()
    parser = argparse.ArgumentParser(description='PRTG Command Line Interface',
                                     epilog=('environment variables:\n' +
                                             '  ' + __ENV_VARNAME_ENDPOINT + '\t\tPRTG endpoint URL\n' +
                                             '  ' + __ENV_VARNAME_USERNAME + '\t\tPRTG username\n' +
                                             '  ' + __ENV_VARNAME_PASSWORD + '\t\tPRTG user password\n\n' +
                                             '  Note: Environment variables are overriden by command-line arguments.'),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['ls', 'status', 'apply'],
                        help='ls: list, status: status, apply: apply rules')
    parser.add_argument('-c', '--content', choices=['groups', 'devices', 'sensors'], default='devices',
                        help='content (default: devices)')
    parser.add_argument('-l', '--level', default=__ARG_DEFAULT_LOGGING_LEVEL,
                        help='Logging level (default: ' + __ARG_DEFAULT_LOGGING_LEVEL + ')')
    parser.add_argument('-f', '--format', choices=['csv', 'pretty'], default='pretty',
                        help='Display format (default: pretty)')
    parser.add_argument('-r', '--rules', default='rules.yaml', help='Rule set filename (default: rules.yaml)')
    parser.add_argument('-e', '--endpoint', default=endpoint, help='PRTG endpoint URL (default: ' + endpoint + ')')
    parser.add_argument('-u', '--username', default=username, help='PRTG username')
    parser.add_argument('-p', '--password', default=password, help='PRTG user password')
    return parser.parse_args()


def main():
    """
    Parse commandline arguments for PRTG-CLI.
    :return: None
    """

    args = get_args()
    print('ENDPOINT:', args.endpoint)

    logging.basicConfig(level=args.level)

    client = Client(endpoint=args.endpoint, username=args.username, password=args.password)

    if args.command == 'ls':
        query = Query(client=client, target='table', content=args.content)
        print(CliResponse(client.query(query), mode=args.format))

    if args.command == 'status':  # TODO: Fix.
        query = Query(client=client, target='getstatus')
        client.query(query)
        print(CliResponse(client.query(query), mode=args.format))

    if args.command == 'apply':
        # TODO: Change this so there is a chain of dependencies.
        # TODO: Change rules so each can specify the content_type to which it applies.
        rules = load_rules(args.rules)
        query = Query(client=client, target='table', content='groups')
        client.query(query)
        if args.content in ['devices', 'sensors']:
            query = Query(client=client, target='table', content='devices')
            client.query(query)
        if args.content == 'sensors':
            query = Query(client=client, target='table', content='sensors')
            client.query(query)
        apply_rules(client, rules, args.content)


if __name__ == '__main__':
    main()
