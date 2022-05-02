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

import os
import time
import uuid

import httpx
from logger import LoggerFactory

from app.config import ConfigClass

_file_mgr_logger = LoggerFactory('folder_manager').get_logger()

# here the global cache is ONLY the temporary solution
cache = {}


class FolderMgr:
    """Folder Manager."""

    def __init__(self, project_code, relative_path):
        self.project_code = project_code
        self.relative_path = relative_path
        self.last_node = None
        self.to_create = []
        self.relations_data = []
        self.zone = ConfigClass.namespace

    async def create(self, creator):
        """create folder nodes and connect them to the parent."""
        try:
            path_splitted = self.relative_path.split('/')
            nl_pairs = (
                [{'name': node, 'level': level} for level, node in enumerate(path_splitted)]
                if len(path_splitted) > 0 and not path_splitted[0] == ''
                else []
            )
            node_chain = []
            read_db_duration = 0
            for name_and_level in nl_pairs:
                folder_relative_path = '/'.join(path_splitted[: name_and_level['level']])
                read_db_start_time = time.time()

                new_node = await get_folder_node(
                    self.project_code, name_and_level['name'], folder_relative_path, creator, self.zone
                )
                # print("Node Name:           ", new_node.folder_name)
                # print("Node relative path:  ", new_node.folder_relative_path)
                # print("Node geid:           ", new_node.global_entity_id)
                # print("Node Exist:          ", new_node.exist)
                if not new_node.exist:
                    # join relative path
                    new_node.folder_name = name_and_level['name']
                    new_node.folder_level = name_and_level['level']
                    # since now we have name folder so will not directly
                    # under project node
                    if name_and_level['level'] == 0:
                        raise Exception("Cannot create folder directly under project node")
                    else:
                        parent_node = node_chain[new_node.folder_level - 1]
                        new_node.folder_parent_geid = parent_node.global_entity_id
                        new_node.folder_parent_name = parent_node.folder_name
                    # create in db if not exist
                    lazy_save = await new_node.lazy_save()
                    self.to_create.append(lazy_save)

                read_db_duration += (time.time() - read_db_start_time)

                node_chain.append(new_node)
                self.last_node = new_node
                # print()

            _file_mgr_logger.warn("Read From db cost " + str(read_db_duration))

            return []
        except Exception:
            raise


async def get_folder_node(project_code, folder_name, folder_relative_path, creator, zone):
    folder_node = FolderNode(project_code, folder_name, folder_relative_path, creator, zone)
    return folder_node


class FolderNode:
    """Folder Node Model."""

    def __init__(self, project_code, folder_name, folder_relative_path, creator, zone):
        self.exist = False

        #
        self.global_entity_id = None
        self.folder_name = folder_name
        self.folder_level = None
        self.folder_parent_geid = None
        self.folder_parent_name = None
        self.folder_creator = creator
        self.zone = zone
        self.project_code = project_code
        self.folder_relative_path = folder_relative_path

        self.read_from_cache(
            folder_relative_path,
            folder_name,
            project_code,
        )
        if not self.exist:
            self.read_from_db(
                folder_relative_path,
                folder_name,
                project_code,
                zone,
                creator,
            )

    def read_from_cache(self, folder_relative_path, folder_name, project_code):
        """read created nodes in the cache."""

        obj_path = os.path.join(
            project_code,
            folder_relative_path,
            folder_name
        )
        found = cache.get(obj_path, None)
        if found:
            self.global_entity_id = found.get("global_entity_id")
            self.folder_parent_geid = found.get("folder_parent_geid")
            self.folder_parent_name = found.get("folder_parent_name")
            self.folder_creator = found.get("folder_creator")
            self.project_code = found.get("project_code")
            self.exist = True
        return self.exist

    # ?
    # why dont we just return the self as dict
    async def lazy_save(self):

        zone_mapping = {
            "greenroom": 0
        }.get(self.zone, 1)

        payload = {
            "id": self.global_entity_id,
            "parent": self.folder_parent_geid,
            "parent_path": self.folder_relative_path,
            "type": "folder",
            "zone": zone_mapping,
            "name": self.folder_name,
            "size": 0,
            "owner": self.folder_creator,
            "container_code": self.project_code,
            "container_type": "project",
            "location_uri": "",
            "version": "",
            "tags": [],
            "dcm_id": "",
        }

        return payload

    # TODO make in to async
    def read_from_db(self, folder_relative_path, folder_name, project_code, zone, creator):
        """read from database."""
        # query = {
        #     'folder_relative_path': folder_relative_path,
        #     'name': folder_name,
        #     'project_code': project_code,
        #     'archived': False,
        # }

        # neo4j_client = Neo4jClient()
        # node_label = ConfigClass.GREEN_ZONE_LABEL if zone == "greenroom" else ConfigClass.CORE_ZONE_LABEL
        # neo4j_node = neo4j_client.get_node(node_label, query)
        # attribute_map = {}
        params = {
            'name': self.folder_name,
            'container_code': project_code,
            'archived': False,
            'zone': 0 if self.zone == 'greenroom' else 1,
            'recursive': True,
        }
        if self.folder_relative_path != '':
            params.update({'parent_path': self.folder_relative_path})

        # node_query_url = ConfigClass.NEO4J_SERVICE + 'nodes/%s/query' % neo4j_zone_label
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(node_query_url, json=payload)

        node_query_url = ConfigClass.METADATA_SERVICE + 'items/search/'
        with httpx.Client() as client:
            response = client.get(node_query_url, params=params)
        nodes = response.json().get("result", [])

        if len(nodes) > 0:
            neo4j_node = nodes[0]
            self.global_entity_id = neo4j_node['id']
            self.folder_name = neo4j_node['name']
            self.folder_parent_geid = ''
            self.folder_parent_name = ''
            self.folder_creator = neo4j_node['owner']
            self.folder_relative_path = neo4j_node['parent_path']
            self.zone = zone
            self.project_code = neo4j_node['container_code']
            self.exist = True

        else:
            self.global_entity_id = str(uuid.uuid4())
            self.folder_name = folder_name
            self.folder_creator = creator
            self.folder_relative_path = folder_relative_path
            self.zone = zone
            self.project_code = project_code

        obj_path = os.path.join(zone, project_code, folder_relative_path, folder_name)
        if len(cache) > 128:
            cache.popitem()
        cache.update({obj_path: self.__dict__})

        return self.__dict__


async def batch_create_4j_foldernodes(folders: list) -> httpx.Response:
    """
    Summary:
        The function will call the entity info service to batch create
        the folder node tree for folder uploading.
    Parameters:
        - folders(list): The list of the folder nodes that should be
            created for the upload.
    Return:
        - http response
    """
    url = ConfigClass.ENTITYINFO_SERVICE + 'folders/batch'
    batch_create_payload = {
        'payload': folders,
        'zone': ConfigClass.GREEN_ZONE_LABEL if
        ConfigClass.namespace == 'greenroom' else ConfigClass.CORE_ZONE_LABEL,
        'link_container': False,
    }
    async with httpx.AsyncClient() as client:
        saved = await client.post(url, json=batch_create_payload, timeout=3600)
        if saved.status_code != 200:
            raise Exception("Fail to create folder in neo4j %s" % (saved.__dict__))
    return saved


async def batch_link_folders(relations: list) -> httpx.Response:
    """
    Summary:
        The function will call the neo4j service to batch create
        the link between all batch created node in batch_create_4j_foldernodes.
    Parameters:
        - relations(list): The list of the link infomation as
            - start_params(string): global entity if from
            - end_params(string): geid
    Return:
        - http response
    """
    data = {
        'payload': relations,
        'params_location': ['start', 'end'],
        'start_label': 'Folder',
        'end_label': 'Folder'
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            ConfigClass.NEO4J_SERVICE + 'relations/own/batch',
            json=data,
            timeout=3600
        )
    if response.status_code != 200:
        raise (Exception('[bulk_link_project Error] {} {}'.format(response.status_code, response.text)))

    return response
