# Copyright (C) 2022 Indoc Research
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# REMOVE IT AFTER MIGRATION <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
from py2neo import Graph
from py2neo.matching import NodeMatcher, RelationshipMatcher

from app.config import ConfigClass


class Neo4jClient(object):

    def __init__(self):
        try:
            self.graph = Graph(
                ConfigClass.NEO4J_URL,
                auth=(ConfigClass.NEO4J_USER, ConfigClass.NEO4J_PASS),
            )
            self.nodes = NodeMatcher(self.graph)
            self.relationships = RelationshipMatcher(self.graph)
        except Exception as e:
            raise e

    def get_node(self, label: str, query: dict):
        node_obj = self.graph.nodes.match(label, **query).first()
        return self.node_2_json(node_obj) if node_obj else None

    def node_2_json(self, obj):
        # print(obj)
        if hasattr(obj, "id"):
            temp = {
                'id': obj.id,
                'labels': list(obj.labels)
            }
        else:
            temp = {
                'id': obj.identity,
                'labels': list(obj.labels)
            }
        # add the all the attribute all together
        temp.update(dict(zip(obj.keys(), obj.values())))

        # update the timestamp
        try:
            temp['time_lastmodified'] = str(temp['time_lastmodified'])[:19]
            temp['time_created'] = str(temp['time_created'])[:19]
        except Exception as e:
            raise e

        return temp
