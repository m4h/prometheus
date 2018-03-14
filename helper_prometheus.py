'''
prometheus_helper module - store common classes used in exporters
'''

import os, sys, logging, optparse
from prometheus_client import start_http_server, Gauge

class PrometheusGaugeMetric(object):
    def __init__(self, name, desc, labels, value, value_converter, logger=None):
        '''
        name            -- metric name (e.g. node_network_status)
        desc            -- metric description
        labels          -- indexes (tuple of strings) in metric_data taken as labels
        value           -- index in metric_data (dict) taken as value for metric
        value_converter -- sometime value may came in mixed format like - 5s, 3GB. We need to convert this value to numeric. Pass a function reference to this converter, can be lambda as well.
        logger          -- instance of logging.Logger class
        '''
        self.gauge = Gauge(name, desc, list(labels))
        self.name = name
        self.labels = labels
        self.value = value
        self.value_converter = value_converter
        self.logger = logger

    def populate(self, metric_data):
        '''
        populate labels and value with data
        metric_data -- dict object
        return      -- metric_labels - dict with label=value, metric_value - converted value
        '''
        try:
            converter = getattr(self, self.value_converter)
        except Exception:
            converter = self.value_converter
        metric_value = converter(metric_data[self.value])
        metric_labels = {}
        for label in self.labels:
            metric_labels[label] = metric_data[label]
        return metric_labels, metric_value

    def print_metric(self, metric_labels, metric_value):
        '''
        build and print metric
        metric_labels -- labels to print
        metric_value  -- value to print
        '''
        if metric_labels:
            label_value = []
            for label, value in metric_labels.iteritems():
                label_value.append('{l}={v}'.format(l=label, v=value))
            # show labels in a log
            text = '{n}{{{lv}}} {v}'.format(n=self.name, lv=', '.join(label_value), v=metric_value)
        else:
            # there are no labels to show
            text = '{n} {v}'.format(n=self.name, v=metric_value)
        if self.logger:
            self.logger.info(text)
        else:
            print '[INFO]: {t}'.format(t=text)
        
    def update(self, metric_data, print_metric=False):
        '''
        update metric with newer data
        metric_data     -- dict with indexes insterested to
        print_metric    -- print metric to stdout (good for dev stage)
        '''
        metric_labels, metric_value = self.populate(metric_data)
        if print_metric:
            self.print_metric(metric_labels, metric_value)
        if self.labels:
            self.gauge.labels(**metric_labels).set(metric_value)
        else:
            self.gauge.set(metric_value)


class PrometheusExporterLoggerError(Exception):
    pass

class PrometheusExporterLogger(logging.Logger):
    def __init__(self, name, path=None, level='ERROR', fmt='%(asctime)s [%(levelname)-5.5s]:  %(message)s'):
        try:
            # resolve textual level to numerical 
            level = getattr(logging, level)
        except Exception:
            raise PrometheusExporterLoggerError('wrong logging level {l}'.format(l=level))
        super(PrometheusExporterLogger, self).__init__(name, level)
        formatter = logging.Formatter(fmt)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        self.addHandler(stream_handler)
        if path:
            file_handler = logging.FileHandler(path)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.addHandler(file_handler)


class PrometheusExporterOptionParserError(Exception):
    pass

class PrometheusExporterOptionParser(object):
    def __init__(self, conf_section='prometheus_exporter'):
        usage = '%prog --conf [--port --interval, --conf-section, --log-file, --log-level]'
        parser = optparse.OptionParser(usage=usage)
        parser.add_option('-p', '--port', type='int', help='port to bind prometheus exporter', default=9100)
        parser.add_option('-i', '--interval', type='int', help='interval to probe nodes and update metrics', default=60)
        parser.add_option('-c', '--conf', type='str', help='path to a conf file')
        parser.add_option('-s', '--conf-section', type='str', help='section in configuration file', default=conf_section)
        parser.add_option('-l', '--log-file', type='str', help='path to a log file', default=None)
        parser.add_option('-L', '--log-level', type='str', help='levels available: DEBUG,INFO,WARNING,ERROR,CRITICAL', default='ERROR')
        opts, args = parser.parse_args()
        if not opts.conf:
            raise PrometheusExporterOptionParserError('configuration file is a required argument')
        if not os.path.isfile(opts.conf):
            raise PrometheusExporterOptionParserError('file {c} do not exists'.format(c=opts.conf))
        self.opts, self.args = opts, args
