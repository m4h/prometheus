'''
teamcity exporter - get aggregated status of a project (group of build configurations) and expose as a metric
aggregated status calculated as follows:
- at least one job in RUNNING state - will return RUNNING
- at least one job in FAILURE state - will return FAILURE
- at least one job in ERROR state - will return ERROR
- at least one job in UNKNOWN state (shouldn't happen) - will return UNKNOWN
- all jobs in SUCCESS state - will return SUCCESS
'''

import sys, time, ConfigParser
from helper_teamcity import TeamCity
from helper_prometheus import PrometheusGaugeMetric, PrometheusExporterOptionParser, PrometheusExporterLogger, start_http_server

if __name__ == '__main__':
    parser = PrometheusExporterOptionParser()
    opts, args = parser.opts, parser.args
    logger = PrometheusExporterLogger('exporter_teamcity', path=opts.log_file, level=opts.log_level)
    # parse config file
    conf = ConfigParser.ConfigParser()
    try:
        conf.read(opts.conf)
        teamcity_url = conf.get(opts.conf_section, 'teamcity_url')
        teamcity_username = conf.get(opts.conf_section, 'teamcity_username')
        teamcity_password = conf.get(opts.conf_section, 'teamcity_password')
        branch = conf.get(opts.conf_section, 'git_branch')
    except Exception as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    # create metrics
    teamcity = TeamCity(teamcity_url, teamcity_username, teamcity_password)
    status_to_num = {'SUCCESS': 0, 'RUNNING': 1, 'ERROR': 2, 'FAILURE': 3, 'UNKNOWN': 4}
    # handling teamcity_build_status metric
    # disabled as it heavily loads teamcity server (query for each build)
    '''
    build_status_metric = PrometheusGaugeMetric(name='teamcity_build_status',
                                                desc='status of a build (build configuration): SUCCESS=0, RUNNING=1, ERROR=2, FAILURE=3, UNKNOWN=4',
                                                labels=('id', 'branch'),
                                                value='status',
                                                value_converter=lambda status: status_to_num[status],
                                                logger=logger)
    '''
    project_status_metric = PrometheusGaugeMetric(name='teamcity_project_aggregated_status',
                                                  desc='aggregated status of all builds (build configuration) for a project: SUCCESS=0, RUNNING=1, ERROR=2, FAILURE=3, UNKNOWN=4',
                                                  labels=('id', 'branch'),
                                                  value='status',
                                                  value_converter=lambda status: status_to_num[status],
                                                  logger=logger)
    queue_metric = PrometheusGaugeMetric(name='teamcity_build_queue_len',
                                         desc='length of build queue (how many agents are waiting)',
                                         labels=(),
                                         value='count',
                                         value_converter=lambda count: count,
                                         logger=logger)
    agents_metric = PrometheusGaugeMetric(name='teamcity_agents_num',
                                          desc='any number (in any state) of agents avaiable',
                                          labels=(),
                                          value='count',
                                          value_converter=lambda count: count,
                                          logger=logger)
    start_http_server(opts.port)
    while True:
        # handling teamcity_build_status metric
        # disabled as it heavily loads teamcity server (query for each build)
        '''
        all_builds = []
        try:
            all_builds = teamcity.get_all_builds()
        except Exception as ex:
            logger.error(ex)
        for build in all_builds:
            build_id = build['id']
            status, display_status = teamcity.get_build_aggregated_status(build_id, branch)
            status_data = build
            status_data['branch'] = branch
            status_data['status'] = display_status
            build_status_metric.update(status_data)
        '''
        # handling teamcity_project_aggregated_status
        projects = []
        try:
            projects = teamcity.get_all_projects()
        except Exception as ex:
            logger.error(ex)
        for project in projects:
            try:
                _id = project['id']
                status, display_status = teamcity.get_project_aggregated_status(_id, branch)
                data = project
                data['branch'] = branch
                data['status'] = display_status
                project_status_metric.update(data)
            except Exception as ex:
                logger.error(ex)
        # handling teamcity_build_queue_len
        queue = {'count': -1}
        try:
            queue['count'] = len(teamcity.get_build_queue())
        except Exception as ex:
            logger.error(ex)
        queue_metric.update(queue)
        # handling teamcity_agents_num
        agents = {'count': -1}
        try:
            agents['count'] = len(teamcity.get_all_agents())
        except Exception as ex:
            logger.error(ex)
        agents_metric.update(agents)
        time.sleep(opts.interval)
