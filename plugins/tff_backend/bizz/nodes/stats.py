# -*- coding: utf-8 -*-
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.4@@
import json
import logging
import time
import types
from collections import defaultdict
from datetime import datetime

from google.appengine.api import apiproxy_stub_map, urlfetch
from google.appengine.ext import ndb
from google.appengine.ext.deferred import deferred

import influxdb
from framework.bizz.job import run_job
from framework.plugin_loader import get_config
from framework.utils import now
from mcfw.cache import cached
from mcfw.consts import MISSING, DEBUG
from mcfw.rpc import returns, arguments
from plugins.its_you_online_auth.bizz.authentication import refresh_jwt
from plugins.its_you_online_auth.models import Profile
from plugins.rogerthat_api.api import system
from plugins.rogerthat_api.exceptions import BusinessException
from plugins.tff_backend.bizz import get_rogerthat_api_key
from plugins.tff_backend.bizz.iyo.utils import get_iyo_username
from plugins.tff_backend.bizz.messages import send_message_and_email
from plugins.tff_backend.bizz.odoo import get_nodes_from_odoo
from plugins.tff_backend.bizz.todo import update_hoster_progress, HosterSteps
from plugins.tff_backend.configuration import InfluxDBConfig
from plugins.tff_backend.consts.hoster import DEBUG_NODE_DATA
from plugins.tff_backend.libs.zero_robot import Task, EnumTaskState
from plugins.tff_backend.models.hoster import NodeOrder, NodeOrderStatus
from plugins.tff_backend.models.user import TffProfile, NodeInfo
from plugins.tff_backend.plugin_consts import NAMESPACE
from plugins.tff_backend.to.nodes import UserNodeStatusTO
from plugins.tff_backend.utils.app import get_app_user_tuple

SKIPPED_STATS_KEYS = ['disk.size.total']


@returns(apiproxy_stub_map.UserRPC)
def _async_zero_robot_call(path, method=urlfetch.GET, payload=None):
    cfg = get_config(NAMESPACE)
    try:
        jwt = _refresh_jwt(cfg.orchestator.jwt)
    except:
        msg = 'Could not refresh JWT'
        logging.exception(msg)
        raise deferred.PermanentTaskFailure(msg)
    headers = {'Cookie': 'caddyoauth=%s' % jwt, 'Content-Type': 'application/json'}
    url = u'https://zero-robot.threefoldtoken.com%s' % path
    rpc = urlfetch.create_rpc(deadline=30)
    urlfetch.make_fetch_call(rpc, payload=payload, method=method, url=url, headers=headers)
    return rpc


@cached(1, 3600)
@returns(unicode)
@arguments(jwt=unicode)
def _refresh_jwt(jwt):
    """
        Cached method to refresh JWT only when it's needed (once every hour, at most)
    Returns:
        unicode
    """
    return refresh_jwt(jwt, 3600)


def _get_task_url(task):
    return '/services/%s/task_list/%s' % (task.service_guid, task.guid)


@returns([object])
@arguments(tasks=[Task], callback=types.FunctionType, deadline=int)
def _wait_for_tasks(tasks, callback=None, deadline=120):
    results = []
    start_time = time.time()
    incomplete_tasks = {t.guid: t for t in tasks}
    while incomplete_tasks:
        rpcs = {task.guid: (task, _async_zero_robot_call(_get_task_url(task)))
                for task in incomplete_tasks.itervalues()}
        time.sleep(10)
        duration = time.time() - start_time
        logging.debug('Waited for %s tasks for %.2f seconds', len(rpcs), duration)
        if duration > deadline:
            logging.info('Deadline of %s seconds exceeded!', deadline)
            break

        incomplete_by_state = defaultdict(list)
        for task, rpc in rpcs.values():
            node_id = task.service_name
            result = rpc.get_result()
            if result.status_code != 200:
                logging.error('/task_list for node %s returned status code %s. Content:\n%s',
                              node_id, result.status_code, result.content)
                del incomplete_tasks[task.guid]
                continue

            task = Task(**json.loads(result.content))
            if task.state in (EnumTaskState.ok, EnumTaskState.error):
                del incomplete_tasks[task.guid]
                results.append(callback(task) if callback else task)
            else:
                incomplete_by_state[task.state].append(task.service_name)

        for state, node_ids in incomplete_by_state.iteritems():
            logging.debug('%s %s task(s) on the following nodes: %s', len(node_ids), state.value,
                          ', '.join(node_ids))

    return results


def _node_status_callback(task):
    status = 'running' if task.state == EnumTaskState.ok else 'halted'
    return task.service_name, status


def get_nodes_status(node_ids):
    tasks = _get_node_info_tasks(node_ids)
    statuses = dict(_wait_for_tasks(tasks, _node_status_callback))
    return [statuses.get(node_id, u'not_found') for node_id in node_ids]


def check_online_nodes():
    run_job(_get_node_orders, [], check_if_node_comes_online, [])


def _get_node_orders():
    return NodeOrder.list_check_online()


def check_if_node_comes_online(order_key):
    order = order_key.get()  # type: NodeOrder
    order_id = order.id
    if not order.odoo_sale_order_id:
        raise BusinessException('Cannot check status of node order without odoo_sale_order_id')
    nodes = get_nodes_from_odoo(order.odoo_sale_order_id)
    if not nodes:
        raise BusinessException('Could not find nodes for sale order %s on odoo' % order_id)

    statuses = get_nodes_status([n['id'] for n in nodes])
    if all([status == 'running' for status in statuses]):
        iyo_username = get_iyo_username(order.app_user)
        _set_node_status_arrived(order_key, iyo_username, nodes)
    else:
        logging.info('Nodes %s from order %s are not all online yet', nodes, order_id)


@ndb.transactional()
def _set_node_status_arrived(order_key, iyo_username, nodes):
    order = order_key.get()
    logging.info('Marking nodes %s from node order %s as arrived', nodes, order_key)
    human_user, app_id = get_app_user_tuple(order.app_user)
    order.populate(arrival_time=now(),
                   status=NodeOrderStatus.ARRIVED)
    order.put()
    deferred.defer(add_nodes_to_profile, iyo_username, nodes, _transactional=True)
    deferred.defer(update_hoster_progress, human_user.email(), app_id, HosterSteps.NODE_POWERED,
                   _transactional=True)


@ndb.transactional()
@returns(TffProfile)
@arguments(iyo_username=unicode, nodes=[dict])
def add_nodes_to_profile(iyo_username, nodes):
    dummy = TffProfile.create_key("threefold_dummy_1").get()
    profile = TffProfile.create_key(iyo_username).get()
    existing_ids = [n.id for n in profile.nodes]
    dummies_to_remove = list()
    for node in nodes:
        if node['id'] not in existing_ids:
            profile.nodes.append(NodeInfo(**node))
        for dni in dummy.nodes:
            if dni.id == node['id']:
                dummies_to_remove.append(dni)
    profile.put()
    if dummies_to_remove:
        for dni in dummies_to_remove:
            dummy.nodes.remove(dni)
        dummy.put()
    user, app_id = get_app_user_tuple(profile.app_user)
    data = {'nodes': [n.to_dict() for n in profile.nodes]}
    deferred.defer(system.put_user_data, get_rogerthat_api_key(), user.email(), app_id, data, _transactional=True)
    return profile


def get_nodes_stats(nodes):
    # type: (list[NodeInfo]) -> list[dict]
    if DEBUG:
        return [_get_stats(DEBUG_NODE_DATA)]

    tasks = _get_node_stats_tasks([node.id for node in nodes])

    results_per_node = {node.id: {'id': node.id,
                                  'status': node.status,
                                  'serial_number': node.serial_number,
                                  'info': None,
                                  'stats': None}
                        for node in nodes}

    for task in _wait_for_tasks(tasks):
        if task.state == EnumTaskState.ok:
            results_per_node[task.service_name][task.action_name] = json.loads(task.result)
        else:
            logging.warn('Task %s on node %s has state ERROR:\n%s: %s\n%s',
                         _get_task_url(task),
                         task.service_name,
                         task.eco and task.eco.exceptionclassname,
                         task.eco and task.eco.errormessage,
                         task.eco and task.eco._traceback)
    return [_get_stats(r) for r in results_per_node.itervalues()]


def get_nodes_for_user(app_user):
    nodes = []
    for order in NodeOrder.list_by_user(app_user):
        if order.status in (NodeOrderStatus.SENT, NodeOrderStatus.ARRIVED):
            nodes.extend(get_nodes_from_odoo(order.odoo_sale_order_id))
    return nodes


def _get_stats(data):
    stats = {}
    if data['stats']:
        for stat_key, values in data['stats'].iteritems():
            last_5_min_stats = values['history']['300']
            stats[stat_key] = last_5_min_stats
    return {
        'id': data['id'],
        'status': data['status'],
        'serial_number': data['serial_number'],
        'info': data.get('info'),
        'stats': stats
    }


def _get_cpu_stats(data, stats_time='300'):
    # Summarize all CPU usages of each core into 1 object
    total_cpu = defaultdict(lambda: {'avg': 0.0, 'count': 0, 'max': 0.0, 'start': 0, 'total': 0.0})
    cpu_count = 0
    for key in data:
        cpu_count += 1
        if key.startswith('machine.CPU.percent'):
            cpu_stats = data[key]['history'].get(stats_time, [])
            for stat_obj in cpu_stats:
                timestamp = stat_obj['start']
                for k in total_cpu[timestamp]:
                    if k == 'start':
                        total_cpu[timestamp][k] = stat_obj[k]
                    else:
                        total_cpu[timestamp][k] += stat_obj[k]
    for timestamp in total_cpu:
        for k in total_cpu[timestamp]:
            if k != 'start':
                total_cpu[timestamp][k] = total_cpu[timestamp][k] / cpu_count
    return sorted(total_cpu.values(), key=lambda v: v['start'])


@returns([Task])
@arguments(node_ids=[unicode])
def _get_node_stats_tasks(node_ids):
    blueprint = {
        'content': {
            'actions': [{
                'template': 'github.com/zero-os/0-templates/node/0.0.1',
                'actions': ['info', 'stats'],
                'service': node_id
            } for node_id in node_ids]
        }
    }
    return _execute_blueprint(json.dumps(blueprint))


@returns([Task])
@arguments(node_ids=[unicode])
def _get_node_info_tasks(node_ids=None):
    if node_ids:
        blueprint = {
            'content': {
                'actions': [{
                    'template': 'github.com/zero-os/0-templates/node/0.0.1',
                    'actions': 'info',
                    'service': node_id
                } for node_id in node_ids]
            }
        }
    else:
        blueprint = {
            'content': {
                'actions': {
                    'template': 'github.com/zero-os/0-templates/node/0.0.1',
                    'actions': 'info'
                }
            }
        }
    return _execute_blueprint(json.dumps(blueprint))


def _execute_blueprint(blueprint):
    logging.debug('Executing blueprint: %s', blueprint)
    result = _async_zero_robot_call('/blueprints', urlfetch.POST, blueprint).get_result()
    msg = '/blueprints returned status code %s. Content:\n%s' % (result.status_code, result.content)
    if result.status_code != 200:
        raise deferred.PermanentTaskFailure(msg)

    logging.debug(msg)
    return [Task(**d) for d in json.loads(result.content)]


def _get_node_statuses(tasks):
    return dict(_wait_for_tasks(tasks, _node_status_callback))  # {node_id: status}


def check_node_statuses():
    tasks = _get_node_info_tasks()
    statuses = _get_node_statuses(tasks)
    run_job(_get_profiles_with_node, [], _check_node_status, [statuses])
    all_tffs = TffProfile.list_all()
    dummy = TffProfile.create_key("threefold_dummy_1").get()
    known_nodes = set()
    for tp in all_tffs:
        for node in tp.nodes:
            known_nodes.add(node.id)
    dummy = TffProfile.create_key("threefold_dummy_1").get()
    dirty = False
    for ns in statuses:
        if not ns in known_nodes:
            ni = NodeInfo()
            ni.id = ns
            ni.serial = "-"
            dummy.nodes.append(ni)
            dirty = True
    if dirty:
        dummy.put()


def _get_profiles_with_node():
    return TffProfile.list_with_node()


@ndb.transactional()
def _check_node_status(tff_profile_key, statuses):
    try:
        tff_profile = tff_profile_key.get()  # type: TffProfile
        should_update = False
        for node in tff_profile.nodes:
            status = statuses.get(node.id)
            if not status:
                logging.warn('Expected to find node %s in the response for user %s', node.id, tff_profile.username)
                continue
            if node.status != status:
                logging.info('Node %s of user %s changed from status "%s" to "%s"',
                             node.id, tff_profile.username, node.status, status)
                should_update = True
                from_status = node.status
                node.status = status

                now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
                if tff_profile.username != 'threefold_dummy_1':
                    _send_node_status_update_message(tff_profile.app_user, from_status, status, now)

        if should_update:
            tff_profile.put()
            deferred.defer(_put_node_status_user_data, tff_profile_key, _transactional=True)
        deferred.defer(_get_and_save_node_stats, tff_profile.nodes, _transactional=True)
    except Exception as e:
        msg = 'Failure in checking node status for %s.' % tff_profile_key
        logging.exception(e.message, _suppress=False)
        raise deferred.PermanentTaskFailure(msg)


def _put_node_status_user_data(tff_profile_key):
    tff_profile = tff_profile_key.get()
    user, app_id = get_app_user_tuple(tff_profile.app_user)
    data = {'nodes': [n.to_dict() for n in tff_profile.nodes]}
    system.put_user_data(get_rogerthat_api_key(), user.email(), app_id, data)


def _send_node_status_update_message(app_user, from_status, to_status, now):
    if from_status == u'running':
        subject = u'Connection to your node has been lost since %s' % now
        msg = u'Dear ThreeFold Member,\n\n' \
              u'Connection to your node has been lost since %s. Please check the network connection of your node.\n' \
              u'Kind regards,\n' \
              u'The ThreeFold Team' % (now)
    elif to_status == u'running':
        subject = u'Connection to your node has been resumed since %s' % now
        msg = u'Dear ThreeFold Member,\n\n' \
              u'Congratulations! Your node is now successfully connected to our system, and has been resumed since %s.\n' \
              u'Kind regards,\n' \
              u'The ThreeFold Team' % (now)
    else:
        logging.debug(
            "_send_node_status_update_message not sending message for status '%s' => '%s'", from_status, to_status)
        return

    send_message_and_email(app_user, msg, subject)


def list_nodes_by_status(status=None):
    # type: (unicode) -> list[UserNodeStatusTO]
    if status:
        qry = TffProfile.list_by_node_status(status)
    else:
        qry = TffProfile.list_with_node()
    tff_profiles = qry.fetch()  # type: list[TffProfile]
    profiles = {profile.username: profile for profile in
                ndb.get_multi([Profile.create_key(p.username) for p in tff_profiles])}
    results = []
    for tff_profile in tff_profiles:
        for node in tff_profile.nodes:
            if node.status == status or not status:
                results.append(UserNodeStatusTO(
                    profile=profiles.get(tff_profile.username).to_dict() if tff_profile.username in profiles else None,
                    node=node.to_dict()))
    return sorted(results, key=lambda k: k.profile and k.profile['info']['firstname'])


def _get_and_save_node_stats(nodes):
    # type: (list[NodeInfo]) -> None
    client = get_influx_client()
    if not client:
        return
    nodes_stats = get_nodes_stats(nodes)
    points = []
    for node in nodes_stats:
        fields = {'id': node['id']}
        if node['info']:
            fields['procs'] = node['info']['procs']
        points.append({
            'measurement': 'node-info',
            'tags': {
                'status': node['status'],
            },
            'time': datetime.now().isoformat() + 'Z',
            'fields': fields
        })
        if node['status'] == 'running' and node['stats']:
            stats = node['stats']
            for stat_key, values in stats.iteritems():
                stat_key_split = stat_key.split('/')
                if stat_key_split[0] in SKIPPED_STATS_KEYS:
                    continue
                tags = {
                    'id': node['id'],
                    'type': stat_key_split[0],
                }
                if len(stat_key_split) == 2:
                    tags['subtype'] = stat_key_split[1]
                for values_on_time in values:
                    points.append({
                        'measurement': 'node-stats',
                        'tags': tags,
                        'time': datetime.utcfromtimestamp(values_on_time['start']).isoformat() + 'Z',
                        'fields': {
                            'max': float(values_on_time['max']),
                            'avg': float(values_on_time['avg'])
                        }
                    })
    logging.info('Writing %s datapoints to influxdb for nodes %s', len(points), nodes)
    client.write_points(points)


def get_influx_client():
    config = get_config(NAMESPACE).influxdb  # type: InfluxDBConfig
    if config is MISSING:
        return None
    return influxdb.InfluxDBClient(config.host, config.port, config.username, config.password, config.database,
                                   config.ssl, config.ssl)


def get_nodes_stats_from_influx(nodes):
    # type: (list[NodeInfo]) -> list[dict]
    client = get_influx_client()
    if not client:
        return []
    stats_per_node = {node.id: dict(stats=[], **node.to_dict()) for node in nodes}
    stat_types = (
        'machine.CPU.percent', 'machine.memory.ram.available', 'network.throughput.incoming',
        'network.throughput.outgoing')
    queries = []
    hours_ago = 6
    statements = []  # type: list[tuple]
    for node in nodes:
        for stat_type in stat_types:
            qry = """SELECT mean("avg") FROM "node-stats" WHERE ("type" = '%(type)s' AND "id" = '%(node_id)s') AND time >= now() - %(hours)dh GROUP BY time(15m)""" % {
                'type': stat_type, 'node_id': node.id, 'hours': hours_ago}
            statements.append((node, stat_type))
            queries.append(qry)
    query_str = ';'.join(queries)
    logging.debug(query_str)
    result_sets = client.query(query_str)
    for statement_id, (node, stat_type) in enumerate(statements):
        for result_set in result_sets:
            if result_set.raw['statement_id'] == statement_id:
                stats_per_node[node.id]['stats'].append({
                    'type': stat_type,
                    'data': result_set.raw.get('series', [])
                })
    return stats_per_node.values()
