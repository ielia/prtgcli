# -*- coding: utf-8 -*-
"""
CLI Tool for Paessler's PRTG (http://www.paessler.com/)
"""

import argparse
import os
import logging
import yaml

from prtg.client import Client
from prtg.models import Query, NameMatch
from prettytable import PrettyTable


def load_config():
    """
    Load config from environment variables.
    :var PRTGENDPOINT: Environment variable indicating PRTG endpoint. Default: 'http://172.20.18.112:8080'.
    :var PRTGUSERNAME: Environment variable indicating PRTG username. Default: 'prtgadmin'.
    :var PRTGPASSWORD: Environment variable indicating PRTG password. Default: 'prtgadmin'.
    :return:
    """
    endpoint = os.getenv('PRTGENDPOINT', 'http://172.20.18.112:8080')
    username = os.getenv('PRTGUSERNAME', 'prtgadmin')
    password = os.getenv('PRTGPASSWORD', 'prtgadmin')
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


def apply_rules(client, rules):
    """
    Apply property change rules.
    :param client: PRTG Client instance.
    :param rules: Rules.
    """

    def get_parent_value(the_prop):
        the_parent_value = []
        if hasattr(device, 'parentid') and device.parentid:
            logging.debug('PARENTID: {}'.format(device.parentid))
            try:
                parent = client.cache.get_object(device.parentid)
                the_parent_value = the_parent_value = parent.__getattribute__(the_prop)
            except KeyError:
                pass
        logging.debug('PARENT: {}'.format(the_parent_value))
        return the_parent_value

    def update_list_value(the_prop, current_parent_value, value):
        current = device.__getattribute__(the_prop)
        current = list(filter(lambda element: element not in current_parent_value, current))
        update = list(filter(lambda element: element not in current and element not in current_parent_value, value))
        the_new_value = ' '.join(current) + ' ' + ' '.join(update)
        return the_new_value

    def get_value(current_parent_value):
        if rule['update']:
            v = update_list_value(rule['prop'], current_parent_value, rule['value'])
        elif rule['value'] is not None:
            v = ' '.join(rule['value'])
        else:
            v = ''
        return v.strip()

    queries = {}
    for device in client.cache.get_content('devices'):
        for rule in rules:
            if NameMatch(device, **rule).evaluate():
                prop = rule['prop']
                parent_value = get_parent_value(rule['prop'])
                new_value = get_value(parent_value)
                query = Query(
                    client, target='setobjectproperty', objid=device.objid, name=prop, value=new_value
                )
                device.update_field(prop, new_value, parent_value)
                queries[(device.objid, prop)] = query

    for query in queries.values():
        client.query(query)


def get_args():
    """
    Get command-line arguments.
    :return: Arguments object.
    """
    parser = argparse.ArgumentParser(description='PRTG Command Line Interface')
    parser.add_argument('command', help='command', choices=['ls', 'status', 'apply'])
    parser.add_argument('-c', '--content', default='devices', help='content', choices=['groups', 'devices', 'sensors'])
    parser.add_argument('-l', '--level', help='Logging level', default='INFO')
    parser.add_argument('-f', '--format', help='Display format', default='pretty', choices=['csv', 'pretty'])
    parser.add_argument('-r', '--rules', help='Modify objects based on rule set', default='../rules.yaml')
    return parser.parse_args()


def main():
    """
    Parse commandline arguments for PRTG-CLI.
    :return: None
    """

    args = get_args()

    logging.basicConfig(level=args.level)

    endpoint, username, password = load_config()

    client = Client(endpoint=endpoint, username=username, password=password)

    if args.command == 'ls':
        query = Query(client=client, target='table', content=args.content)
        print(CliResponse(client.query(query), mode=args.format))

    if args.command == 'status':  # TODO: Fix.
        query = Query(client=client, target='getstatus')
        client.query(query)
        print(CliResponse(client.query(query), mode=args.format))

    if args.command == 'apply':
        rules = load_rules(args.rules)
        # Load groups in cache
        query = Query(client=client, target='table', content='groups')
        client.query(query)
        # Load devices in cache
        query = Query(client=client, target='table', content='devices')
        client.query(query)
        apply_rules(client, rules)


if __name__ == '__main__':
    main()
