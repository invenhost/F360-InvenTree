
import unicodedata
import re
import traceback

import adsk

from .apper import apper
from . import config


# https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename
def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def error(typ_str=None):
    """ shows message box when error raised """
    # generate error message
    if typ_str == 'cmd':
        ret_msg = 'Command executed failed: {}'.format(traceback.format_exc())
    else:
        ret_msg = 'Failed:\n{}'.format(traceback.format_exc())

    # show message
    ao = apper.AppObjects()
    if ao.ui:
        ao.ui.messageBox(ret_msg)
    else:
        print(ret_msg)


def get_cmd(ao, key):
    ref_name = f'{config.company_name}_{config.app_name}_{key}'
    return ao.ui.commandDefinitions.itemById(ref_name)

@apper.lib_import(config.lib_path)
def create_f360_part(component: adsk.fusion.Component, cat: str):
    """ create part based on occurence """
    from inventree.part import Part
    from . import functions

    ao = apper.AppObjects()

    # build up args
    part_kargs = {
        'name': component.name,
        'description': component.description if component.description else 'None',
        'IPN': component.partNumber,
        'active': True,
        'virtual': False,
    }
    # add category if set
    if cat:
        part_kargs.update({'category': cat.pk})
    # create part itself
    part = Part.create(functions.inv_api(), part_kargs)
    # check if part created - else raise error
    if not part:
        ao.ui.messageBox('Error occured during API-call')
        return
    elif not part.pk:
        error_detail = [f'<strong>{a}</strong>\n{b[0]}' for a, b in part._data.items()]
        ao.ui.messageBox(f'Error occured:<br><br>{"<br>".join(error_detail)}')
        return

    write_f360_parameters(part, component)

    return part

@apper.lib_import(config.lib_path)
def write_f360_parameters(part, component: adsk.fusion.Component):    
    from .functions import Fusion360Parameters

    physicalProperties = component.physicalProperties

    Fusion360Parameters.ID.value.create_parameter(part, component.id)
    Fusion360Parameters.AREA.value.create_parameter(part, physicalProperties.area)
    Fusion360Parameters.VOLUME.value.create_parameter(part, physicalProperties.volume)
    Fusion360Parameters.MASS.value.create_parameter(part, physicalProperties.mass)
    Fusion360Parameters.DENSITY.value.create_parameter(part, physicalProperties.density)

    if component.material and component.material.name:
        Fusion360Parameters.MATERIAL.value.create_parameter(part, component.material.name)

    axis = ['x', 'y', 'z']
    bb_min = {a: getattr(component.boundingBox.minPoint, a) for a in axis}
    bb_max = {a: getattr(component.boundingBox.maxPoint, a) for a in axis}
    bb = {a: bb_max[a] - bb_min[a] for a in axis}

    Fusion360Parameters.BOUNDING_BOX_WIDTH.value.create_parameter(part, bb["x"])
    Fusion360Parameters.BOUNDING_BOX_HEIGHT.value.create_parameter(part, bb["y"])
    Fusion360Parameters.BOUNDING_BOX_DEPTH.value.create_parameter(part, bb["z"])
