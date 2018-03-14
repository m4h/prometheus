'''
teamcity_helper - store classes used in teamcity exporter
'''

import json, requests
from requests.auth import HTTPBasicAuth

class TeamCityURL(object):
    ''' builds a API request URL from args '''
    def __init__(self, base, args=[]):
        self.base = base
        self.args = []
        self.add_args(*args)
    
    def add_arg(self, arg):
        if hasattr(arg, 'to_string'):
            arg = arg.to_string()
        self.args.append(arg)

    def add_args(self, *args):
        for arg in args:
            self.add_arg(arg)

    def to_string(self):
        base = self.base
        args = '&'.join(self.args)
        return '{base}?{args}'.format(base=base, args=args)

class TeamCityField(object):
    ''' builds a query field. e.g. - fields=count,build(status,state,running) '''
    def __init__(self, *args):
        self.arg = 'fields'
        self.fields = []
        self.add_fields(*args)

    def add_field(self, field):
        if hasattr(field, 'to_string'):
            field = field.to_string()
        self.fields.append(field)

    def add_fields(self, *args):
        for field in args:
            self.add_field(field)

    def to_string(self):
        arg = self.arg
        fields = ','.join(self.fields)
        return '{arg}={fields}'.format(arg=arg, fields=fields)

class TeamCityLocator(object):
    ''' builds a query locator. e.g. - locator=affectedProject:(id:CiAcmeBuild) '''
    def __init__(self, name, **kwargs):
        self.arg = 'locator'
        self.name = name
        self.filters = []
        self.add_filters(**kwargs)

    def add_filters(self, **kwargs):
        for name, value in kwargs.iteritems():
            _filter = ':'.join([name, value])
            self.filters.append(_filter)

    def to_string(self):
        arg = self.arg
        name = self.name
        filters = ','.join(self.filters)
        return '{arg}={name}:({filters})'.format(arg=arg, name=name, filters=filters)

class TeamCityObjectLocator(object):
    ''' builds an object locator. e.g. - $locator(running:any,branch:development,count:1) '''
    def __init__(self, **kwargs):
        self.name = '$locator'
        self.filters = []
        self.add_filters(**kwargs)

    def add_filters(self, **kwargs):
        for name, value in kwargs.iteritems():
            _filter = ':'.join([name, value])
            self.filters.append(_filter)

    def to_string(self):
        name = self.name
        filters = ','.join(self.filters)
        return '{name}({filters})'.format(name=name, filters=filters)

class TeamCityObject(object):
    ''' builds a query object. e.g. - build(status,state,running) '''
    def __init__(self, name, properties=[]):
        self.name = name
        self.properties = []
        self.add_properties(*properties)

    def add_property(self, prop):
        if hasattr(prop, 'to_string'):
            prop = prop.to_string()
        self.properties.append(prop)

    def add_properties(self, *args):
        for prop in args:
            self.add_property(prop)

    def to_string(self):
        name = self.name
        properties = ','.join(self.properties)
        return '{name}({properties})'.format(name=name, properties=properties)

class TeamCityHelperError(Exception):
    ''' exceptor '''
    pass

class TeamCityHelper(object):
    ''' used by flask and prometheus exporter to get build/project status '''

    def __init__(self, url, username, password, debug=False):
        '''
        url      -- is a base url to teamcity server (e.g. http://teamcity:8080)
        username -- username 
        password -- password
        '''
        self.url = url
        self.username = username
        self.password = password
        self.debug = debug

    def teamcity_api(self, url, headers={'Accept': 'application/json'}, **kwargs):
        '''
        makes api call against teamcity server and return parsed json 
        
        url     -- api query URL
        headers -- Accept: 'application/json' is required to get json response from teamcity
        return  -- response as dictionary and response code (200, 404, e.g.)
        '''
        auth = HTTPBasicAuth(self.username, self.password)
        if self.debug: 
            '[DEBUG]: teamcity_api sending request - {url}'.format(url=url)
        resp = requests.get(url, headers=headers, auth=auth, **kwargs)
        if self.debug: 
            '[DEBUG]: teamcity_api got response code - {code}'.format(code=resp.status_code)
        try:
            data = json.loads(resp.text)
            if self.debug:
                '[DEBUG]: teamcity_api got response text:\n{text}'.format(text=resp.text)
        except Exception as ex:
            err = 'teamcity_api failed:\n'
            err += 'exception: {message}\n'.format(message=ex.message)
            err += 'request url: {url}\n'.format(url=url)
            err += 'response code: {code}\n'.format(code=resp.status_code)
            err += 'response text: {text}'.format(text=resp.text)
            if self.debug: 
                '[DEBUG]: teamcity_api got exception:\n{err}'.format(err=err)
            raise TeamCityHelperError(err)
        return data, resp.status_code

    def aggregate_status(self, statuses, states):
        ''' aggregate statuses and return desired display status and teamcity original status '''
        display = teamcity_status = 'UNKNOWN' # by default assume UNKNOWN
        status = {'FAILURE': 0, 'ERROR': 0, 'SUCCESS': 0, 'UNKNOWN': 0}
        state  = {'running': 0, 'queued': 0, 'finished': 0}
        # accumulate statuses and states in a dict
        for code in statuses:
            status.setdefault(code, 0)
            status[code] += 1
        for code in states:
            state.setdefault(code, 0)
            state[code] += 1
        if status['FAILURE'] > 0: # most severe - if some build has a FAILURE - everything considered as FAILURE
            teamcity_status = display = 'FAILURE'
        elif status['ERROR'] > 0: # same as for FAILURE
            teamcity_status = display = 'ERROR'
        elif status['SUCCESS'] > 0: 
            teamcity_status = display = 'SUCCESS'

        if state['running'] > 0: # if some build is running - consider everything as running (like step is not finished yet)
            display = 'RUNNING'
        elif state['queued'] > 0: 
            display = 'QUEUED'
        return teamcity_status, display

    def get_build_aggregated_status(self, name, branch=None):
        ''' much of code crafts an url and requests teamcity for latest build status (for particular job) '''
        statuses = states = []
        # filter by this locator
        builds_locator = TeamCityObjectLocator(running='any', count='1')
        if branch:
            builds_locator.add_filters(branch=branch)
        # fetch particular properties for a build
        build = TeamCityObject(name='build', properties=['status', 'state', 'running', 'branchName'])
        # collection of builds
        builds = TeamCityObject(name='builds', properties=[builds_locator, build, 'count'])
        # fields part of url 
        fields = TeamCityField(builds)
        # create actual url object
        url = TeamCityURL('{url}/httpAuth/app/rest/buildTypes/id:{name}'.format(url=self.url, name=name), args=[fields])
        # make an api call
        resp, code = self.teamcity_api(url.to_string())
        try:
            if resp['builds']['count'] > 0:
                for build in resp['builds']['build']:
                    statuses.append(build['status'])
                    states.append(build['state'])
            status, state = self.aggregate_status(statuses, states)
        except Exception as ex:
            err = 'build_aggregated_status:\n'
            err += 'exception: {message}\n'.format(message=ex.message)
            err += 'request url: {url}\n'.format(url=url)
            err += 'response code: {code}\n'.format(code=code)
            err += 'response text: {text}'.format(text=resp)
            raise TeamCityHelperError(err)
        return (status, state)

    def get_project_aggregated_status(self, name, branch=None):
        ''' much of code crafts an url and requests teamcity for project latest build statuses '''
        statuses = states = []
        locator = TeamCityLocator(name='affectedProject', id=name)
        builds_locator = TeamCityObjectLocator(running='any', count='1')
        if branch:
            builds_locator.add_filters(branch=branch)
        build = TeamCityObject(name='build', properties=['status', 'state', 'running', 'branchName'])
        builds = TeamCityObject(name='builds', properties=[builds_locator, build, 'count'])
        build_type = TeamCityObject(name='buildType', properties=['id', 'name', builds])
        fields = TeamCityField('count', build_type)
        url = TeamCityURL('{url}/httpAuth/app/rest/buildTypes'.format(url=self.url), args=[locator, fields])
        resp, code = self.teamcity_api(url.to_string())
        try:
            if resp['count'] > 0: # collect all statuses and states for later processing
                for build_type in resp['buildType']:
                    if build_type['builds']['count'] > 0:
                        for build in build_type['builds']['build']:
                            statuses.append(build['status'])
                            states.append(build['state'])
            status, display_status = self.aggregate_status(statuses, states)
        except Exception as ex:
            err = 'build_aggregated_status:\n'
            err += 'exception: {message}\n'.format(message=ex.message)
            err += 'request url: {url}\n'.format(url=url)
            err += 'response code: {code}\n'.format(code=code)
            err += 'response text: {text}'.format(text=resp)
            raise TeamCityHelperError(err)
        return (status, display_status)

    def get_all_projects(self):
        project = TeamCityObject(name='project', properties=['id', 'name'])
        fields = TeamCityField('count', project)
        url = TeamCityURL('{url}/httpAuth/app/rest/projects'.format(url=self.url), args=[fields])
        resp, code = self.teamcity_api(url.to_string())
        return resp['project']

    def get_all_builds(self):
        build_type = TeamCityObject(name='buildType', properties=['id', 'name'])
        fields = TeamCityField('count', build_type)
        url = TeamCityURL('{url}/httpAuth/app/rest/buildTypes'.format(url=self.url), args=[fields])
        resp, code = self.teamcity_api(url.to_string())
        return resp['buildType']

    def get_all_agents(self):
        pool = TeamCityObject(name='pool', properties=['id', 'name'])
        agent = TeamCityObject(name='agent', properties=['id', 'name', 'connected', 'enabled', 'authorized', 'ip', pool])
        fields = TeamCityField('count', agent)
        url = TeamCityURL('{url}/httpAuth/app/rest/agents'.format(url=self.url), args=[fields])
        resp, code = self.teamcity_api(url.to_string())
        return resp['agent']

    def get_build_queue(self):
        build = TeamCityObject(name='build', properties=['id', 'buildTypeId', 'branchName'])
        fields = TeamCityField('count', build)
        url = TeamCityURL('{url}/httpAuth/app/rest/buildQueue'.format(url=self.url), args=[fields])
        resp, code = self.teamcity_api(url.to_string())
        return resp['build']
        
class TeamCity(TeamCityHelper): 
    ''' just an alias to TeamCityHelper '''
    pass
