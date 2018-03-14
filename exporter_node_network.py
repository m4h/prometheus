'''
node exporter - take a list of nodes, probe them on particular port, measure dns resolution time and expose metrics
'''

import sys, time, socket, ConfigParser
from helper_teamcity import TeamCity
from helper_prometheus import PrometheusGaugeMetric, PrometheusExporterOptionParser, PrometheusExporterLogger, start_http_server

def get_teamcity_agents(url, username, password):
    teamcity = TeamCity(url, username, password)
    agents = teamcity.get_all_agents()
    host_names = []
    for agent in agents:
        if agent['authorized'] and agent['connected'] and agent['enabled']:
            host_names.append(agent['name'])
    return host_names
   
def resolve_host(host):
    try:
        ip = socket.gethostbyname(host)
    except Exception as ex:
        ip = None
    return ip

def probe_host(host, port, timeout=2):
    is_up = False
    resolve_start = time.time()
    ip = resolve_host(host)
    resolve_end = time.time()
    # resolve_time in ms
    resolve_time = '%.2f' % ((resolve_end - resolve_start) * 1000)
    if ip:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                is_up = True
        finally:
            s.close()
    return {'resolve_time': resolve_time, 'host': host, 'port': port, 'up': is_up}


if __name__ == '__main__':
    parser = PrometheusExporterOptionParser()
    opts, args = parser.opts, parser.args
    logger = PrometheusExporterLogger('exporter_node_network', path=opts.log_file, level=opts.log_level)
    # parse config file
    conf = ConfigParser.ConfigParser()
    conf.read(opts.conf)
    try:
        teamcity_url = conf.get(opts.conf_section, 'teamcity_url')
        teamcity_username = conf.get(opts.conf_section, 'teamcity_username')
        teamcity_password = conf.get(opts.conf_section, 'teamcity_password')
        teamcity_probe_port = conf.getint(opts.conf_section, 'teamcity_probe_port')
        probe_nodes = conf.get(opts.conf_section, 'probe_nodes').split(',')
        probe_port = conf.getint(opts.conf_section, 'probe_port')
    except ConfigParser.NoSectionError as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    except ConfigParser.NoOptionError as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    # create metrics
    # metric for network status (node up or down)
    metric_node = PrometheusGaugeMetric(name='node_network_status',
                                        desc='node is up or down - 1 is up, 0 is down',
                                        labels=('host','port'),
                                        value='up',
                                        value_converter=lambda x:int(x),
                                        logger=logger)
    # metric for dns resolution time (for particular node)
    metric_dns = PrometheusGaugeMetric(name='node_network_resolution_time',
                                       desc='dns resultion time in ms',
                                       labels=('host','port'),
                                       value='resolve_time',
                                       value_converter=lambda x:x,
                                       logger=logger)
    # serve updated metrics
    start_http_server(opts.port)
    while True:
        try:
            # dynamically fetch teamcity agents
            agents = get_teamcity_agents(teamcity_url, teamcity_username, teamcity_password)
        except Exception as ex:
            logger.error('failed to get teamcity agents.\n{e}'.format(e=ex))
            agents = []
        # create a new list which will include agents and probe_nodes (from config)
        nodes = list(probe_nodes)
        for agent in agents:
            # create host:port pair for teamcity agents
            pair = '{n}:{p}'.format(n=agent, p=teamcity_probe_port)
            nodes.append(pair)
        # probe and update metrics
        for node in nodes:
            try:
                # we can specify both node:port or just node
                host, port = node.split(':')
            except ValueError:
                # for those who don't have port we attach 'default' probe_port
                host, port = node, probe_port
            # do a probe and update metrics
            metric_data = probe_host(host, int(port))
            metric_node.update(metric_data)
            metric_dns.update(metric_data)
        time.sleep(opts.interval)
