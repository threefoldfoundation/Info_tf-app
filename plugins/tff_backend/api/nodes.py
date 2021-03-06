# -*- coding: utf-8 -*-
# Copyright 2017 GIG Technology NV
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
# @@license_version:1.3@@
from google.appengine.api.search import MAXIMUM_DOCUMENTS_RETURNED_PER_SEARCH

from mcfw.restapi import rest
from mcfw.rpc import returns, arguments
from plugins.tff_backend.bizz.audit.audit import audit
from plugins.tff_backend.bizz.audit.mapping import AuditLogType
from plugins.tff_backend.bizz.authentication import Scopes
from plugins.tff_backend.bizz.nodes.hoster import put_node_order, create_node_order
from plugins.tff_backend.bizz.nodes.stats import list_nodes, get_node, update_node, delete_node, create_node
from plugins.tff_backend.dal.node_orders import search_node_orders, get_node_order, list_node_orders_by_user
from plugins.tff_backend.to.nodes import NodeOrderListTO, CreateNodeOrderTO, NodeOrderTO, UpdateNodePayloadTO, \
    CreateNodeTO
from plugins.tff_backend.utils.search import sanitise_search_query


@rest('/orders', 'get', Scopes.BACKEND_READONLY, silent_result=True)
@returns(NodeOrderListTO)
@arguments(page_size=(int, long), cursor=unicode, query=unicode, status=(int, long), username=unicode)
def api_get_node_orders(page_size=20, cursor=None, query=None, status=None, username=None):
    page_size = min(page_size, MAXIMUM_DOCUMENTS_RETURNED_PER_SEARCH)
    filters = {'status': status, 'username': username}
    if username and not query and status is None:
        results = [NodeOrderTO.from_model(model) for model in list_node_orders_by_user(username)]
        return NodeOrderListTO(cursor=None, more=False, results=results)
    return NodeOrderListTO.from_search(*search_node_orders(sanitise_search_query(query, filters), page_size, cursor))


@rest('/orders/<order_id:[^/]+>', 'get', Scopes.BACKEND_READONLY)
@returns(NodeOrderTO)
@arguments(order_id=(int, long))
def api_get_node_order(order_id):
    return NodeOrderTO.from_dict(get_node_order(order_id).to_dict())


@rest('/orders', 'post', Scopes.BACKEND_ADMIN)
@returns(NodeOrderTO)
@arguments(data=CreateNodeOrderTO)
def api_create_node_order(data):
    return NodeOrderTO.from_dict(create_node_order(data).to_dict())


@audit(AuditLogType.UPDATE_NODE_ORDER, 'order_id')
@rest('/orders/<order_id:[^/]+>', 'put', Scopes.BACKEND_ADMIN)
@returns(NodeOrderTO)
@arguments(order_id=(int, long), data=NodeOrderTO)
def api_put_node_order(order_id, data):
    return NodeOrderTO.from_dict(put_node_order(order_id, data).to_dict())


@rest('/nodes', 'get', Scopes.NODES_READONLY, silent_result=True)
@returns([dict])
@arguments(sort_by=unicode, direction=unicode)
def api_list_nodes(sort_by=None, direction=None):
    return list_nodes(sort_by, direction == 'asc')


@rest('/nodes', 'post', Scopes.NODES_ADMIN, silent_result=True)
@returns(dict)
@arguments(data=CreateNodeTO)
def api_create_node(data):
    return create_node(data).to_dict()


@rest('/nodes/<node_id:[^/]+>', 'get', Scopes.NODES_READONLY, silent_result=True)
@returns(dict)
@arguments(node_id=unicode)
def api_get_node(node_id):
    return get_node(node_id).to_dict()


@audit(AuditLogType.UPDATE_NODE, 'node_id')
@rest('/nodes/<node_id:[^/]+>', 'put', Scopes.NODES_ADMIN, silent_result=True)
@returns(dict)
@arguments(node_id=unicode, data=UpdateNodePayloadTO)
def api_update_node(node_id, data):
    return update_node(node_id, data).to_dict()


@rest('/nodes/<node_id:[^/]+>', 'delete', Scopes.NODES_ADMIN, silent_result=True)
@returns()
@arguments(node_id=unicode)
def api_delete_node(node_id):
    return delete_node(node_id)
