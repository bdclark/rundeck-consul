# rundeck-consul

A simple Python Bottle app that presents Consul nodes and services as RunDeck
resource and option models.

*** THIS IS A WORK IN PROGRESS! *** Currently I'm only testing and using it
internally.

## Requirements
* bottle
* requests

## Endpoints
* `/resource` - Returns a Rundeck [resource-json-v10][1] formatted resource
  model of Consul nodes and services.
* `/option/services` - Returns a simple [json-formatted][2] list of Consul services
  for use as a Rundeck option model provider. The following optional parameters are
  allowed (and multiple can be used together):
  * `tag` - return services that have a given tag
  * `tags` - return all services matching (comma-separated) list of tags
  * `dc` - return services in a given datacenter
  * `startswith` - return services that start with given string
  * `contains` - return services that contain the given string
  * `endswith` - only return services that contain a given string

##### Project-specific endpoints
Optional projects can be configured (for example multiple consul clusters
or environments):
* `/resource/<project>`
* `/option/services/<project>`

## Running
Run `./app.py`, or if using a configuration file (see below),
`./app.py /path/to/config.json`. How to keep it running is up to you.

## Configuration File
The configuration file is optional. If provided it should follow the format
indicated below. If not provided the app will listen on `0.0.0.0:8080` and
will attempt to connect to consul at `localhost:8500`.

* `app` - listen address and port for this app
* `consul`
  * `host` `port` `token` - consul connection params
  * `datacenters` - only include certain datacenters in resource
  * `services` - only include certain services
  * `exclude` - return all services except for these

If `datacenters`, `services`, and `exclude` are not provided, queries to `/resource`
will return all services in all datacenters.

Example:
```
{
  "app": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "consul": {
    "host": "localhost",
    "port": "8500",
    "token": "optionalsecret",
    "datacenters": ["dc1", "dc2"],
    "services": ["service1", "service2"],
    "exclude": ["excluded_service1"]
  },
  "projects": {
    "dev": {
      "host": "consul-dev.example.place",
      "token": "abc123"
      ...
    }
    ...
  }
}
```

[1]: http://rundeck.org/docs/man5/resource-json.html
[2]: http://rundeck.org/docs/manual/jobs.html#json-format
