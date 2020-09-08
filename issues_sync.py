#!/usr/local/bin/python3
#
# sonar-tools
# Copyright (C) 2019-2020 Olivier Korach
# mailto:olivier.korach AT gmail DOT com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
'''
    This script propagates the manual issue changes (FP, WF, Change
    of severity, of issue type, comments) from:
    - One project to another (normally on different platforms but not necessarily)
    - One branch of a project to another branch of the same project (normally LLBs)

    Only issues with a 100% match are propagates. When there's a doubt, nothing is done
'''


import sys
import sonarqube.env as env
import sonarqube.issues as issues
import sonarqube.utilities as util


def parse_args(desc):
    parser = util.set_common_args(desc)
    parser = util.set_component_args(parser)
    parser = util.set_target_args(parser)
    parser.add_argument('-r', '--recover', required=False,
                        help='''What information to replicate. Default is FP and WF, but issue assignment,
                        tags, severity and type change can be recovered too''')
    parser.add_argument('-b', '--sourceBranch', required=False, help='Name of the source branch')
    parser.add_argument('-B', '--targetBranch', required=False, help='Name of the target branch')
    parser.add_argument('-K', '--targetComponentKeys', required=False,
                        help='''key of the target project when synchronizing 2 projects
                        or 2 branches on a same platform''')
    return parser.parse_args()


args = parse_args('Replicates issue history between 2 same projects on 2 SonarQube platforms or 2 branches')
source_env = env.Environment(url=args.url, token=args.token)
if args.urlTarget is None:
    args.urlTarget = args.url
if args.tokenTarget is None:
    args.tokenTarget = args.token

if (args.sourceBranch is None and args.targetBranch is not None or
        args.sourceBranch is not None and args.targetBranch is None):
    util.logger.error("Both source and target branches should be specified, aborting")
    sys.exit(2)

target_env = env.Environment(url=args.urlTarget, token=args.tokenTarget)

params = vars(args)
util.check_environment(params)
for key in params.copy():
    if params[key] is None:
        del params[key]
params['projectKey'] = params['componentKeys']
targetParams = params.copy()
if 'targetComponentKeys' in targetParams and targetParams['targetComponentKeys'] is not None:
    targetParams['projectKey'] = targetParams['targetComponentKeys']
    targetParams['componentKeys'] = targetParams['targetComponentKeys']
# Add SQ environment

params.update({'env': source_env})
all_source_issues = issues.search_all_issues(source_env, **params)
util.logger.info("Found %d issues with manual changes on source project", len(all_source_issues))

targetParams.update({'env': target_env})
all_target_issues = issues.search_all_issues(target_env, **targetParams)
util.logger.info("Found %d target issues on target project", len(all_target_issues))

for issue in all_target_issues:
    util.logger.info('Searching sibling for issue %s', issue.get_url())
    siblings = issues.search_siblings(issue, all_source_issues, False,
                                      params['componentKeys'] == targetParams['componentKeys'])
    nb_siblings = len(siblings)
    util.logger.info('Found %d sibling(s) for issue %s', nb_siblings, str(issue))
    if nb_siblings == 0:
        continue
    if nb_siblings > 1:
        util.logger.info('Ambiguity for issue key %s, cannot automatically apply changelog', str(issue))
        util.logger.info('Candidate issue keys below:')
        for sibling in siblings:
            util.logger.debug(sibling.id)
        continue
    # Exactly 1 match
    util.logger.info('Found a match, issue %s', siblings[0].get_url())
    if siblings[0].has_changelog_or_comments():
        util.logger.info('Automatically applying changelog to issue %s', issue)
        issues.apply_changelog(issue, siblings[0])
    else:
        util.logger.info('No changelog to apply')
