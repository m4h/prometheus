'''
chef node - exporter which expose info about chef nodes.
NOT IN USE
'''

from __future__ import print_function
import subprocess
import json
import shlex
import time
from prometheus_client import start_http_server, Gauge


class ChefNodeOhaiTime(object):
    def __init__(self, server_url, user, key, knife='knife', query='*:*'):
        self.knife = knife
        self.query = query
        self.user = user
        self.key = key
        self.server_url = server_url
        self.gauge = Gauge('chef_node_ohai_time',
                           'time in epoch seconds of last successful run (ohai_time)',
                           ['name',
                            'chef_environment',
                            'run_list',
                            'ipaddress',
                            'platform',
                            'platform_version'])

    def __knife(self, path='tc-ubu-03.json'):
        with open(path) as f:
            lines = ''.join(f.readlines())
            return json.loads(lines)

    def knife_search(self, server_url, user, key, knife='knife', query='*:*'):
        '''
        query a chef server 
    
        knife       -- path to knife binary
        query       -- knife query
        server_url  -- chef server url (https://HOST:PORT/organizations/ORG)
        user        -- chef user
        key         -- path to user key
        return      -- result in a json format
        '''
        args = '''{0} search {1} --server-url={2} --key={3} --user={4} --format=json'''.format(knife, query, server_url, key, user)
        args = shlex.split(args)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        sout, serr = proc.communicate()
        if proc.returncode:
            raise Exception(sout)
        data = json.loads(sout)
        return data

    def node_to_metric(self, node):
        '''
        extract information from chef node object
        
        node    -- chef node object
        return  -- extracted information and ohai_time
        '''
        ohai = node['automatic']
        ohai_time = int(ohai['ohai_time'])
        metric = {'name': node['name'],
                  'chef_environment': node['chef_environment'],
                  'run_list': ','.join(node['run_list']),
                  'ipaddress': ohai['ipaddress'],
                  'platform': ohai['platform'],
                  'platform_version': ohai['platform_version']}
        return metric, ohai_time

    def update_metric(self):
        '''
        query chef server and update metric with newer data
        '''
        #search_result = self.__knife()
        search_result = self.knife_search(knife=self.knife,
                                          query=self.query,
                                          user=self.user,
                                          key=self.key,
                                          server_url=self.server_url)
        nodes = search_result['rows']
        for node in nodes:
            metric, ohai_time = self.node_to_metric(node)
            print(metric, ohai_time)
            self.gauge.labels(metric['name'],
                              metric['chef_environment'],
                              metric['run_list'],
                              metric['ipaddress'],
                              metric['platform'],
                              metric['platform_version']).set(ohai_time)


if __name__ == '__main__':
    knife_server_url = 'https://chef-server-12/organizations/acme'
    knife_user = 'deployer'
    knife_key = '~/.knife/chef-12-integ.pem'
    #knife_key = '~/.knife/chef-12-prod1.pem'
    prom_listen_port = 9191
    prom_query_interval = 60

    chef_node_ohai_time = ChefNodeOhaiTime(server_url=knife_server_url, user=knife_user, key=knife_key)
    start_http_server(prom_listen_port)
    while True:
        chef_node_ohai_time.update_metric()
        time.sleep(prom_query_interval)
