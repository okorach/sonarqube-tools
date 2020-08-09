#!/usr/local/bin/python3
'''

    Abstraction of the SonarQube "quality profile" concept

'''
import sys
import datetime
import re
import json
import pytz
import sonarqube.sqobject as sq
import sonarqube.env as env
import sonarqube.rules as rules
import sonarqube.utilities as util

class QualityGate(sq.SqObject):

    def __init__(self, key, endpoint, data=None):
        super().__init__(key=key, env=endpoint)
        if data is None:
            return
        self.name = data['name']
        self.is_default = data['isDefault']
        self.is_built_in = data['isBuiltIn']
        resp = env.get('qualitygates/show', ctxt=self.env, params={'id': self.key})
        data = json.loads(resp.text)
        self.conditions = []
        self.projects = None
        for c in data.get('conditions', []):
            self.conditions.append(c)

    def get_projects(self):
        if self.projects is None:
            self.projects = self.search()
        return self.projects

    def count_projects(self):
        _ = self.get_projects()
        return len(self.projects)

    def __audit_conditions__(self):
        issues = 0
        for c in self.conditions:
            m = c['metric']
            if re.match('new_', c['metric']):
                continue
            if (m == 'reliability_rating' or m == 'security_rating') and int(c['error']) >= 4:
                continue
            issues += 1
        if issues > 0:
            util.logger.warning("Quality gate %s has problematic conditions on overall code", self.name)
        return issues

    def audit(self):
        util.logger.info("Auditing quality gate %s", self.name)
        issues = 0
        if self.is_built_in:
            return 0
        nb_conditions = len(self.conditions)
        if nb_conditions == 0:
            util.logger.warning("Quality gate %s has no conditions defined, this is useless", self.name)
            issues += 1
        elif nb_conditions > 7:
            util.logger.warning("Quality gate %s has %d conditions defined, this is more than the 7 max recommended",
                                self.name, len(self.conditions))
            issues += 1
        issues += self.__audit_conditions__()
        if self.is_default:
            return issues
        projects = self.get_projects()
        if not projects:
            util.logger.warning("Quality gate %s is not used by any project, it should be deleted", self.name)
            issues += 1
        return issues

    def count(self, params=None):
        if params is None:
            params = {}
        params['gateId'] = self.key
        params['ps'] = 1
        resp = env.get('qualitygates/search', ctxt=self.env, params=params)
        data = json.loads(resp.text)
        return data['paging']['total']

    def search(self, page=0, params=None):
        if params is None:
            params = {}
        params['ps'] = 500
        if page != 0:
            params['p'] = page
            resp = env.get('qualitygates/search', ctxt=self.env, params=params)
            data = json.loads(resp.text)
            return data['results']

        nb_proj = self.count(params=params)
        nb_pages = (nb_proj+499)//500
        prj_list = {}
        for p in range(nb_pages):
            params['p'] = p+1
            for prj in self.search(page=p+1, params=params):
                prj_list[prj['key']] = prj
        return prj_list

def list_qg(endpoint=None):
    resp = env.get('qualitygates/list', ctxt=endpoint)
    data = json.loads(resp.text)
    qg_list = []
    for qg in data['qualitygates']:
        qg_list.append(QualityGate(key=qg['id'], endpoint=endpoint, data=qg))
    return qg_list

def audit(endpoint=None):
    util.logger.info("Auditing quality gates")
    issues = 0
    quality_gates_list = list_qg(endpoint)
    nb_qg = len(quality_gates_list)
    if nb_qg > 5:
        util.logger.warning("There are %d quality gates, this is more than the max 5 recommended", nb_qg)
    for qp in quality_gates_list:
        issues += qp.audit()
    return issues