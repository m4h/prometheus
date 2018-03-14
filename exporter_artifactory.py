'''
artifactory exporter - fetches storageinfo data from artifactory, convert to numeric values and expose as metrics
'''

import requests, subprocess, json, shlex, time, ConfigParser
from requests.auth import HTTPBasicAuth
from helper_prometheus import PrometheusGaugeMetric, PrometheusExporterLogger, PrometheusExporterOptionParser, start_http_server

def artifactory_api(url, username, password):
    '''
    call to artifactory api
    url      -- url to api endpoint
    username -- artifactory user
    password -- artifactory pass
    return   -- response text (json) and status code (200, 301 and etc)
    '''
    auth = HTTPBasicAuth(username, password)
    resp = requests.get(url, auth=auth)
    return resp.text, resp.status_code

def text_to_int(text):
    '''
    artifactory api return humanized value which should be converted to int
    convert textual value to int
    text    -- text value
    return  -- int
    '''
    return round(int(text.replace(',', '')), 3)

def text_to_bytes(text):
    '''
    artifactory api return humanized value which should be converted to int
    convert textual value to int (bytes)
    text    -- text value
    return  -- bytes
    '''
    _bytes = 0
    amount, unit = text.lower().split()[:2]
    if unit == 'gb':
        _bytes = float(amount) * 1024 ** 3
    elif unit == 'mb':
        _bytes = float(amount) * 1024 ** 2
    elif unit == 'kb':
        _bytes = float(amount) * 1024 ** 1
    return round(int(_bytes), 3)

def text_to_percent(text):
    '''
    artifactory api return humanized value which should be converted to int
    convert textual value with  '%' to int 
    text    -- text value
    return  -- int
    '''
    return float(text.strip('%'))

if __name__ == '__main__':
    parser = PrometheusExporterOptionParser()
    opts, args = parser.opts, parser.args
    logger = PrometheusExporterLogger('exporter_artifactory', path=opts.log_file, level=opts.log_level)
    # parse config file
    conf = ConfigParser.ConfigParser()
    conf.read(opts.conf)
    try:
        api_url = conf.get(opts.conf_section, 'api_url')
        api_username = conf.get(opts.conf_section, 'api_username')
        api_password = conf.get(opts.conf_section, 'api_password')
    except ConfigParser.NoSectionError as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    except ConfigParser.NoOptionError as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    # create metrics
    filestore_metrics = []
    filestore_metrics.append(PrometheusGaugeMetric(name='artifactory_filestore_free_space',
                                                   desc='filestore free space in bytes',
                                                   labels=('storageDirectory','storageType'),
                                                   value='freeSpace',
                                                   value_converter=text_to_bytes,
                                                   logger=logger))
    filestore_metrics.append(PrometheusGaugeMetric(name='artifactory_filestore_used_space',
                                                   desc='filestore used space in bytes',
                                                   labels=('storageDirectory','storageType'),
                                                   value='usedSpace',
                                                   value_converter=text_to_bytes,
                                                   logger=logger))
    filestore_metrics.append(PrometheusGaugeMetric(name='artifactory_filestore_total_space',
                                                   desc='filestore total space in bytes',
                                                   labels=('storageDirectory','storageType'),
                                                   value='totalSpace',
                                                   value_converter=text_to_bytes,
                                                   logger=logger))
    binaries_metrics = []
    binaries_metrics.append(PrometheusGaugeMetric(name='artifactory_binaries_artifacts_count',
                                                  desc='number of artifacts',
                                                  labels=(),
                                                  value='artifactsCount',
                                                  value_converter=text_to_int,
                                                  logger=logger))
    binaries_metrics.append(PrometheusGaugeMetric(name='artifactory_binaries_artifacts_size',
                                                  desc='the amount of physical storage that would be occupied if each artifact was a physical binary (not just a link) in bytes',
                                                  labels=(),
                                                  value='artifactsSize',
                                                  value_converter=text_to_bytes,
                                                  logger=logger))
    binaries_metrics.append(PrometheusGaugeMetric(name='artifactory_binaries_binaries_count',
                                                  desc='the total number of physical binaries stored in your system',
                                                  labels=(),
                                                  value='binariesCount',
                                                  value_converter=text_to_int,
                                                  logger=logger))
    binaries_metrics.append(PrometheusGaugeMetric(name='artifactory_binaries_binaries_size',
                                                  desc='the amount of physical storage occupied by the binaries in your system in bytes',
                                                  labels=(),
                                                  value='binariesSize',
                                                  value_converter=text_to_bytes,
                                                  logger=logger))
    binaries_metrics.append(PrometheusGaugeMetric(name='artifactory_binaries_items_count',
                                                  desc='the total number of items (both files and folders) in your system',
                                                  labels=(),
                                                  value='itemsCount',
                                                  value_converter=text_to_int,
                                                  logger=logger))
    repository_metrics = []
    repository_metrics.append(PrometheusGaugeMetric(name='artifactory_repository_files_count',
                                                    desc='the total number of files in this repository',
                                                    labels=('packageType','repoKey','repoType'),
                                                    value='filesCount',
                                                    value_converter=int,
                                                    logger=logger))
    repository_metrics.append(PrometheusGaugeMetric(name='artifactory_repository_folders_count',
                                                    desc='the total number of folders in this repository',
                                                    labels=('packageType','repoKey','repoType'),
                                                    value='foldersCount',
                                                    value_converter=int,
                                                    logger=logger))
    repository_metrics.append(PrometheusGaugeMetric(name='artifactory_repository_items_count',
                                                    desc='the total number of items (folders and files) in this repository',
                                                    labels=('packageType','repoKey','repoType'),
                                                    value='itemsCount',
                                                    value_converter=int,
                                                    logger=logger))
    repository_metrics.append(PrometheusGaugeMetric(name='artifactory_repository_used_space',
                                                    desc='repository used space in bytes',
                                                    labels=('packageType','repoKey','repoType'),
                                                    value='usedSpace',
                                                    value_converter=text_to_bytes,
                                                    logger=logger))
    repository_metrics.append(PrometheusGaugeMetric(name='artifactory_repository_percentage',
                                                    desc='the percentage of the total available space occupied by this repository',
                                                    labels=('packageType','repoKey','repoType'),
                                                    value='percentage',
                                                    value_converter=text_to_percent,
                                                    logger=logger))
    start_http_server(opts.port)
    while True:
        try:
            resp, code = artifactory_api(api_url, api_username, api_password)
            api_resp = json.loads(resp)
        except Exception as ex:
            # log error on failure
            logger.error(ex)
            # wait 
            time.sleep(opts.interval)
            # skip that cycle
            continue
        try:
            # handling artifactory_file_store_* metrics
            filestore_summary = api_resp['fileStoreSummary']
            for metric in filestore_metrics:
                metric.update(filestore_summary)
        except Exception as ex:
            logger.error(ex)
        try:
            # handling artifactory_binaries_* metrics
            binaries_summary = api_resp['binariesSummary']
            for metric in binaries_metrics:
                metric.update(binaries_summary)
        except Exception as ex:
            logger.error(ex)
        try:
            # handling artifactory_repository_* metrics
            for repo_summary in api_resp['repositoriesSummaryList']:
                # there is TOTAL repository which do not contain all keys
                if not 'packageType' in repo_summary.keys():
                    continue
                for metric in repository_metrics:
                    metric.update(repo_summary)
        except Exception as ex:
            logger.error(ex)
        time.sleep(opts.interval)
