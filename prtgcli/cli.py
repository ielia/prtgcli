# -*- coding: utf-8 -*-
"""
CLI Tool for Paessler's PRTG (http://www.paessler.com/)
"""

import argparse
from urllib.error import HTTPError
import csvkit
import logging
import os
import sys
import yaml

from prtg.client import Client, PrtgEncoder
from prtg.models import CONTENT_TYPE_ALL, CONTENT_TYPES, Query
from prtg.rules import RuleChain
from prettytable import PrettyTable


__ARG_DEFAULT_LOGGING_LEVEL = 'WARN'
__ENV_VARNAME_ENDPOINT = 'PRTGENDPOINT'
__ENV_VARNAME_USERNAME = 'PRTGUSERNAME'
__ENV_VARNAME_PASSWORD = 'PRTGPASSWORD'
__MAX_BUFFER_SIZE = 500
__ON_QUERY_HTTP_ERROR_ABORT = False


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
    # TODO: Change this so there is a chain of dependencies.
    # TODO: Change rules so each can specify the content_type to which it applies.
    return yaml.load(open(rule_path).read())['rules']


class CliResponse(object):
    """
    PRTG client response object. To be used once per command.
    """

    def __init__(self, entities, mode='pretty', sort_by=None):
        """
        :param entities: Entities coming from cache.
        :param mode: Print (data presentation) mode: 'csv' or 'pretty'.
        :param sort_by: Sorting column name (e.g.: 'objid').
        """
        self.mode = mode
        self.sort_by = sort_by
        self.response = []

        columns = set()

        for entity in entities:
            item = {}
            self.response.append(item)
            for key, value in entity.__dict__.items():
                if key not in ['active', 'changed']:
                    columns.add(key)
                    if isinstance(value, list):
                        item[key] = ' '.join(value)
                    else:
                        item[key] = str(value)

        self.columns = list(columns)
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
                _lst.append(','.join([resp.get(x, '') for x in self.columns]))
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
                p.add_row([resp.get(x, '') for x in self.columns])
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
        except (KeyError, EOFError) as error:
            logging.debug('Got an error {} looking for: {}.'.format(type(error), entity.parentid))
    logging.debug('PARENT: {}'.format(parent))
    return parent


def cache_content(client, source_filename):
    buffer = []
    for entity in csvkit.DictReader(open(source_filename)):
        buffer.append(PrtgEncoder.encode_dict(entity, entity['type'].lower() + 's'))
        if len(buffer) >= __MAX_BUFFER_SIZE:
            client.cache.write_content(buffer, True)
            buffer.clear()
    if buffer:
        client.cache.write_content(buffer, True)


def fetch_and_cache_necessary_content(client, source_filename, content_type):
    """
    Make the appropriate queries to cache all the necessary content to preview/apply rules.
    :param client: PRTG Client instance.
    :param source_filename: Source CSV filename to use instead of PRTG queries.
    :param content_type: Content type, i.e., one of {groups, devices, sensors}.
    """
    if source_filename:
        cache_content(client, source_filename)
    elif content_type == CONTENT_TYPE_ALL:
        fetch_and_cache_specific_content(client, content_type)
    else:
        fetch_and_cache_specific_content(client, *CONTENT_TYPES[:CONTENT_TYPES.index(content_type)+1])


def fetch_and_cache_specific_content(client, content_type, *args):
    if content_type == CONTENT_TYPE_ALL:
        fetch_and_cache_specific_content(client, *CONTENT_TYPES)
    else:
        query = Query(client=client, target='table', content=content_type)
        client.query(query)
        for content_type in args:
            query = Query(client=client, target='table', content=content_type)
            client.query(query)


def run_rules(client, rules, content_type, show=False):
    """
    Runs the rules against the local cache.
    :param client: PRTG Client instance.
    :param rules: Rule dictionaries list.
    :param content_type: Content type, i.e., one of {groups, devices, sensors}.
    :param show: Boolean flag indicating whether to print the queries or not.
    :yield: The list of changes (URLs with full authentication credentials).
    """
    rule_chain = RuleChain(*rules)

    change_map = {}
    count = 0
    for entity in client.cache.get_content(content_type):
        logging.debug('Entity to be processed (count={}): {}'.format(count, entity))
        changes_to_entity = rule_chain.apply(entity, _get_parent(client, entity))
        if changes_to_entity:
            change_map[entity.objid] = changes_to_entity
            client.cache.write_content([entity], True)
        logging.debug('Effective changes: {}'.format(changes_to_entity))

    for objid, changes in change_map.items():
        for prop, new_value in changes.items():
            query = Query(client, target='setobjectproperty', objid=objid, name=prop, value=new_value)
            if show:
                print(query)
            yield query


def apply_rules(client, rules, content_type, show=False):
    """
    Apply property change rules.
    :param client: PRTG Client instance.
    :param rules: Rule dictionaries list.
    :param content_type: Content type, i.e., one of {groups, devices, sensors}.
    :param show: Boolean flag indicating whether to print the queries or not.
    """
    for query in run_rules(client, rules, content_type, show):
        try:
            client.query(query)
        except HTTPError:
            logging.error('Failed applying rules to objid {} prop "{}"'.format(query.extra['id'], query.extra['name']))
            if __ON_QUERY_HTTP_ERROR_ABORT:
                logging.fatal('ABORTED RUN')
                raise


def run_through_rules(client, rules, content_type, show=False):
    """
    Runs the rules against the local cache. The difference between this method and 'run_rules' is that this one consumes
    the latter in order to force execution.
    :param client: PRTG Client instance.
    :param rules: Rule dictionaries list.
    :param content_type: Content type, i.e., one of {groups, devices, sensors}.
    :param show: Boolean flag indicating whether to print the queries or not.
    """
    for query in run_rules(client, rules, content_type, show):  # Forcing execution
        pass
    if show:
        print()


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
    parser.add_argument('command', choices=['ls', 'status', 'preview', 'preview-changed-only', 'apply'],
                        help='ls: list, status: status, preview: preview rule application, apply: apply rules.')
    parser.add_argument('-c', '--content', choices=['groups', 'devices', 'sensors', 'all'], default='devices',
                        help='content (default: devices).')
    parser.add_argument('-l', '--level', default=__ARG_DEFAULT_LOGGING_LEVEL,
                        help='Logging level (default: ' + __ARG_DEFAULT_LOGGING_LEVEL + ').')
    parser.add_argument('-L', '--log-file', default=None, help='Log file (if not set, log will be written to console).')
    parser.add_argument('-f', '--format', choices=['csv', 'pretty'], default='pretty',
                        help='Display format (default: pretty).')
    parser.add_argument('-r', '--rules', default='rules.yaml', help='Rule set filename (default: rules.yaml)')
    parser.add_argument('-s', '--source-file', default=None,
                        help="Uses a source CSV file instead of querying PRTG. "
                             "This option doesn't allow applying rules, but just previewing them.")
    parser.add_argument('-e', '--endpoint', default=endpoint, help='PRTG endpoint URL (default: ' + endpoint + ').')
    parser.add_argument('-u', '--username', default=username, help='PRTG username.')
    parser.add_argument('-p', '--password', default=password, help='PRTG user password.')
    parser.add_argument('-q', '--show-queries', action='store_true',
                        help='Shows the query URLs when previewing or applying rules.')
    return parser.parse_args()


def configure_logging(level, log_file=None):
    log_format = '%(asctime)s %(levelname)s:%(name)s: %(message)s'
    if log_file:
        logging.basicConfig(filename=log_file, level=level, format=log_format)
    else:
        logging.basicConfig(level=level, format=log_format)


def main():
    """
    Parse commandline arguments for PRTG-CLI.
    :return: None
    """

    args = get_args()

    configure_logging(args.level, args.log_file)

    logging.info('----- PRTG-CLI STARTED -----')

    if args.source_file is not None:
        print('SOURCE FILE:', args.source_file)
    else:
        print('ENDPOINT:', args.endpoint)

    client = Client(endpoint=args.endpoint, username=args.username, password=args.password)

    if args.command == 'ls':
        if args.source_file:
            cache_content(client, args.source_file)
        else:
            fetch_and_cache_specific_content(client, args.content)
        print(CliResponse(client.cache.get_content(args.content), mode=args.format))

    if args.command == 'status':  # FIXME
        query = Query(client=client, target='getstatus')
        client.query(query)
        print(CliResponse(client.query(query), mode=args.format))

    if args.command == 'preview':
        rules = load_rules(args.rules)
        fetch_and_cache_necessary_content(client, args.source_file, args.content)
        print()
        run_through_rules(client, rules, args.content, args.show_queries)
        print(CliResponse(client.cache.get_content(args.content), mode=args.format))

    if args.command == 'preview-changed-only':
        rules = load_rules(args.rules)
        fetch_and_cache_necessary_content(client, args.source_file, args.content)
        print()
        run_through_rules(client, rules, args.content, args.show_queries)
        print(CliResponse(client.cache.get_changed_content(args.content), mode=args.format))

    if args.command == 'apply':
        if args.source_file:
            print('Cannot apply rules when a source file is specified.', file=sys.stderr)
        else:
            rules = load_rules(args.rules)
            fetch_and_cache_necessary_content(client, args.source_file, args.content)
            apply_rules(client, rules, args.content, args.show_queries)

    logging.info('----- PRTG-CLI FINISHED -----')


if __name__ == '__main__':
    main()
