#!/usr/bin/env python

import os
import bottle
from bottle import route, run, error, abort, response, request
import argparse
import json
import requests


def consul_get(config, endpoint, dc=None):
    try:
        host = config.get('host', 'localhost')
        port = config.get('port', 8500)
        token = config.get('token', None)
        url = "http://{}:{}/v1{}".format(host, port, endpoint)
        payload = {'token': token, 'dc': dc}
        # print "consul request - url: {} payload: {}".format(url, payload)
        r = requests.get(url, params=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError as e:
        abort(500, "Connection to Consul at {} failed".format(url))
    except requests.exceptions.HTTPError as e:
        abort(r.status_code, "Consul error: {}".format(r.text))


def get_datacenters(config, dc=None):
    return consul_get(config, '/catalog/datacenters', dc)


# if dc specificied, return as list, otherwise get datacenters from config
# if none in config, return all datacenters
def get_datacenters(config, dc=None):
    datacenters = [dc] if dc else config.get('datacenters', [])
    if not datacenters:
        datacenters = consul_get(config, '/catalog/datacenters')
    return datacenters


class ServiceMap:
    def __init__(self):
        self.address_name = {}
        self.address_tags = {}
        self.address_dc = {}

    def add(self, config, service_name, dc):
        append_tags = config.get('append_tags', True)
        for s in consul_get(config, '/catalog/service/' + service_name, dc):
            service_name = s['ServiceName']
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

    def get(self, config):
        node_attributes = config.get('node_attributes', {})
        output = []
        for a, t in self.address_tags.iteritems():
            node = {
                'nodename': self.address_name[a],
                'hostname': a,
                'tags': sorted(list(t)),
                'datacenter': self.address_dc[a]
            }
            # assign additional node attributes from config
            for k, v in node_attributes.iteritems():
                node[k] = v
            output.append(node)
        return output


def build_service_map(config):
    services = config.get('services', [])
    exclude = config.get('exclude', [])
    service_map = ServiceMap()
    try:
        datacenters = get_datacenters(config)
        for dc in datacenters:
            if services:
                for i in services:
                    service_map.add(config, i, dc)
            else:
                dc_services = consul_get(config, '/catalog/services', dc)
                for service_name, tags in dc_services.iteritems():
                    if service_name in exclude:
                        continue
                    service_map.add(config, service_name, dc)
        return service_map.get(config)
    except requests.exceptions.ConnectionError as e:
        abort(500, 'Connection to Consul failed')


# (filtered) list of services from Consul
def service_list(config, options={}):
    tag = options.get('tag')
    tags = options.get('tags')
    tags = tags.split(',') if tags else []
    startswith = options.get('startswith')
    endswith = options.get('endswith')
    contains = options.get('contains')
    datacenter = options.get('dc')
    try:
        datacenters = get_datacenters(config, datacenter)
        output = []
        for dc in datacenters:
            dc_services = consul_get(config, '/catalog/services', dc)
            for s, t in dc_services.iteritems():
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
                output.append(s)
        return sorted(output)
    except requests.exceptions.ConnectionError:
        abort(500, 'Connection to Consul failed')


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
def error404(error):
    response.content_type = 'application/json'
    return json.dumps({'status': 'error', 'code': 500, 'message': error.body})


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
    parser.add_argument('config', metavar='PATH', help='path to config file')
    args = parser.parse_args()
    config = {}
    with open(args.config) as fp:
        config = json.load(fp)
    config.setdefault('listen_host', '0.0.0.0')
    config.setdefault('listen_port', os.getenv('RUNDECK_CONSUL_PORT', 8080))
    config.setdefault('debug', False)
    config.setdefault('host', 'localhost')
    config.setdefault('port', 8500)
    config.setdefault('token', None)
    run(host=config['listen_host'],
        port=config['listen_port'],
        debug=config['debug'])
