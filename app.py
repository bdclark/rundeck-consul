import argparse
import json
import os
import re
import urllib.parse
import consul as consulapi
from bottle import route, run, error, abort, response, request
import logging

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


# if dc specificied, return as list, otherwise get datacenters from config
# if none in config, return all datacenters
def get_datacenters(consul, dc=None):
    datacenters = [dc] if dc else config.get('datacenters', [])
    if not datacenters:
        datacenters = consul.catalog.datacenters()
    return datacenters


# get an instance of a Consul client based on configuration object
def consul_client(config={}):
    config.setdefault('consul', {})
    return consulapi.Consul(
        host=config['consul'].get('host', '127.0.0.1'),
        port=config['consul'].get('port', 8500),
        token=config['consul'].get('token', None),
        scheme=config['consul'].get('scheme', 'http'),
        verify=config['consul'].get('verify', True),
        cert=config['consul'].get('cert', None),
    )


class ServiceMap:
    def __init__(self, config, consul):
        self.config = config
        self.consul = consul
        self.address_name = {}
        self.address_tags = {}
        self.address_dc = {}

    def add(self, service_name, dc):
        append_tags = self.config.get('append_tags', True)
        _, instances = self.consul.catalog.service(service_name, dc=dc)
        for s in instances:
            # service_name = s['ServiceName']
            name = s['Node']
            address = s['Address']
            self.address_name[address] = name
            self.address_dc[address] = dc
            if address not in self.address_tags:
                self.address_tags[address] = set()
            # Add "virtual" tag for service name
            self.address_tags[address].add(service_name)
            for t in s['ServiceTags']:
                if append_tags:
                    # Append service tags to each "virtual" service
                    service_tag = "{}:{}".format(service_name, t)
                    self.address_tags[address].add(service_tag)
                else:
                    # add service tags directly to node
                    self.address_tags[address].add(t)

    def get(self):
        node_attributes = self.config.get('node_attributes', {})
        output = []
        for a, t in self.address_tags.items():
            node = {
                'nodename': self.address_name[a],
                'hostname': a,
                'tags': sorted(list(t)),
                'datacenter': self.address_dc[a]
            }
            # assign additional node attributes from config
            for k, v in node_attributes.items():
                node[k] = v
            output.append(node)
        return output


def build_service_map(config):
    consul = consul_client(config.get('consul', {}))
    services = config.get('services', [])
    exclude = config.get('exclude', [])
    service_map = ServiceMap(config, consul)
    try:
        datacenters = get_datacenters(consul)
        for dc in datacenters:
            if services:
                for i in services:
                    service_map.add(i, dc)
            else:
                _, dc_services = consul.catalog.services(dc=dc)
                for service_name, tags in dc_services.items():
                    if service_name in exclude:
                        continue
                    service_map.add(service_name, dc)
        return service_map.get()
    except Exception as e:
        logging.exception(e)
        abort(500, e)


# (filtered) list of services from Consul
def service_list(config, options={}):
    consul = consul_client(config.get('consul', {}))
    tag = options.get('tag')
    tags = options.get('tags').split(',') if options.get('tags') else []
    startswith = options.get('startswith')
    endswith = options.get('endswith')
    contains = options.get('contains')
    datacenter = options.get('dc')
    regex = options.get('regex')
    if regex:
        regex = urllib.parse.unquote(options.get('regex'))
    try:
        datacenters = get_datacenters(consul, datacenter)
        output = []
        for dc in datacenters:
            idx, dc_services = consul.catalog.services(dc=dc)
            for s, t in dc_services.items():
                if tags and not set(tags) & set(t):
                    continue
                if tag and tag not in t:
                    continue
                if startswith and not s.startswith(startswith):
                    continue
                if endswith and not s.endswith(endswith):
                    continue
                if contains and contains not in s:
                    continue
                if regex and not re.search(regex, s):
                    continue
                output.append(s)
        return output
    except Exception as e:
        logging.exception(e)
        abort(500, e)


def jsonify(data, pretty=False):
    if pretty:
        return json.dumps(data, sort_keys=True, indent=2,
                          separators=(',', ': ')) + "\n"
    else:
        return json.dumps(data) + "\n"


@error(404)
def error404(error):
    response.content_type = 'application/json'
    return json.dumps({'status': 'error', 'code': 404, 'message': error.body})


@error(500)
def error500(error):
    response.content_type = 'application/json'
    return json.dumps({'status': 'error', 'code': 500, 'message': error.body})


@route('/heartbeat')
def heartbeat():
    response.status = 204
    return


@route('/resource')
def index():
    data = build_service_map(config)
    response.content_type = 'application/json'
    return jsonify(data, request.query.pretty)


@route('/resource/<project>')
def project(project):
    if config['projects'] and project in config['projects']:
        project_config = config['projects'][project]
        response.content_type = 'application/json'
        data = build_service_map(project_config)
        return jsonify(data, request.query.pretty)
    else:
        abort(404, "Not found:  '/project/{}'".format(project))


@route('/services')
def services():
    response.content_type = 'application/json'
    data = service_list(config, request.query)
    return jsonify(data, request.query.pretty)


@route('/services/<project>')
def services_project(project):
    if config['projects'] and project in config['projects']:
        project_config = config['projects'][project]
        response.content_type = 'application/json'
        data = service_list(project_config, request.query)
        return jsonify(data, request.query.pretty)
    else:
        abort(404, "Not found:  '/services/{}'".format(project))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', metavar='PATH', help='path to config file')
    parser.add_argument('--debug', action='store_true', help='enable debug')
    args = parser.parse_args()

    config = {}
    if args.config:
        with open(args.config) as fp:
            config = json.load(fp)

    run(host=config.get('host', '0.0.0.0'),
        port=config.get('port', os.getenv('RUNDECK_CONSUL_PORT', 8080)),
        debug=args.debug)
