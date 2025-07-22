import os
from pathlib import Path
from pydantic import validate_call
from uuid import UUID

#from label_studio_sdk.client import LabelStudio

from . import constants
from .models import get_panorma_path


def get_image_paths(dir):
    return [path for path in Path(dir).rglob(
        f'{constants.IMAGES_PREFIX}*')]


def get_image_strs(dir):
    return [str(v) for v in get_image_paths(dir)]


@validate_call
def get_extract_path(guid: UUID):
    return os.path.join(constants.MEDIA_PATH, str(guid))


def get_pano_path(extract_dir):

    panorama_path = get_panorma_path(extract_dir)
    if not panorama_path:
        new_filename = constants.PANO_NAME_BASE
    else:
        filename = os.path.splitext(os.path.basename(panorama_path))[0]
        if filename == constants.PANO_NAME_BASE:
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                           '1'
        else:
            filenumber = int(filename.replace(constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR, ''))
            filenumber += 1
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                           str(filenumber)

    return os.path.join(extract_dir, new_filename + constants.PANO_EXTENSION)


@validate_call
def send_label_studio(guids: list[UUID]):
    # local dev
    api_token = '273f90bb7501f179b8fe2bff8c669700fef1a221'
    api_url = 'http://localhost:8080/'

    #ls = LabelStudio(base_url=api_url, api_key=api_token)
    project = 'SAHI'

    def get_projects(self):
        # get existing projects
        result = {}
        created_projects = self.ls.projects.list()
        for i in created_projects:
            result.update({i.title: i.id})
        print(result)
        # ensure project is a project
        if self.project not in result.keys():
            print('Warning: {0} is not a project.'.format(
                self.project))
            return None
        return result

    projects = get_projects()
    if project not in projects.keys():
        print(f'Did not find project {project}, ending....')
        return None

