import adsk.core
import adsk.fusion
import adsk.cam

import configparser
import os
from enum import Enum

from .apper import apper
from . import config


class Fusion360Template:
    SEPARATOR = ":"
    # Base parameter name
    BASE = "Fusion360" + SEPARATOR
    # Bounding box
    BOUNDING_BOX_BASE = BASE + "BoundingBox" + SEPARATOR

    def __init__(self, name, unit=None):
        self.name = name
        self.unit = unit

    @apper.lib_import(config.lib_path)
    def create_template(self):
        from inventree.base import ParameterTemplate

        ParameterTemplate.create(inv_api(), {
            "name": self.name,
            "units": self.unit or ""
        })

    @apper.lib_import(config.lib_path)
    def create_parameter(self, part, data):
        from inventree.base import Parameter

        Parameter.create(inv_api(), {'part': part.pk, 'template': self.pk, 'data': data})

    @apper.lib_import(config.lib_path)
    def update_parameter(self, part, data):
        from inventree.base import Parameter

        param = Parameter.list(inv_api(), {
            "part": part.pk,
            "template": self.pk
        })[0]

        param.save({
            "data": data
        })

    __PART_TEMPLATE_CACHE = {}

    def cache_part_templates(templates):
        for template in templates:
            Fusion360Template.__PART_TEMPLATE_CACHE[template.name] = template

    @property
    def pk(self):
        return Fusion360Template.__PART_TEMPLATE_CACHE[self.name].pk


class Fusion360Parameters(Enum):
    ID = Fusion360Template(Fusion360Template.BASE + "Id", "UUID")
    # Physical properties name
    AREA = Fusion360Template(Fusion360Template.BASE + "Area", "cm2")
    VOLUME = Fusion360Template(Fusion360Template.BASE + "Volume", "cm3")
    MASS = Fusion360Template(Fusion360Template.BASE + "Mass", "kg")
    DENSITY = Fusion360Template(Fusion360Template.BASE + "Density", "kg/cm3")
    MATERIAL = Fusion360Template(Fusion360Template.BASE + "Material")
    # Bounding box
    BOUNDING_BOX_WIDTH = Fusion360Template(Fusion360Template.BOUNDING_BOX_BASE + "Width", "cm")
    BOUNDING_BOX_HEIGHT = Fusion360Template(Fusion360Template.BOUNDING_BOX_BASE + "Height", "cm")
    BOUNDING_BOX_DEPTH = Fusion360Template(Fusion360Template.BOUNDING_BOX_BASE + "Depth", "cm")


@apper.lib_import(config.lib_path)
def init_Fusion360():
    from inventree.base import ParameterTemplate

    existing = [parameter.name for parameter in ParameterTemplate.list(inv_api())]
    for variant in Fusion360Parameters:
        template = variant.value

        if template.name in existing:
            continue

        template.create_template()
        print("Created non-existing parameter template " + template.name)

    Fusion360Template.cache_part_templates(ParameterTemplate.list(inv_api()))


# region tracking
@apper.lib_import(config.lib_path)
def init_sentry():
    import sentry_sdk

    sentry_sdk.init(
        "https://8b2c118182cd4d43bd6efe3f211b9595@o1047628.ingest.sentry.io/6024677",
        traces_sample_rate=1.0,
        release="0.0.2",
    )
    config.app_tracking = sentry_sdk
# end region


# region config
def load_config(ui: adsk.core.UserInterface):
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf.ini')

    if os.path.exists(config_path) is False:
        TITLE =  "InventreeLink - Initialisation"

        POSTFACE = (
            "It seems InvenTreeLink was not yet properly configured.\n"
            "Please provide the necessary information prompted by the\n"
            "next couple of input boxes.\n"
        )

        def ask_user(line, default=""):
            (value, cancelled) = ui.inputBox(
                line, 
                TITLE, 
                default
            )
                
            return value if not cancelled and value is not "" else None

        ui.messageBox(POSTFACE)

        address = ask_user(
            "Please enter the server address of the InvenTree instance.", 
        )

        if address is None:
            ui.messageBox("Invalid address", TITLE)
            return False               

        token = ask_user(
            "Please enter the user token:"
        )

        if token is None:
            ui.messageBox("Invalid token", TITLE)
            return False

        part_category = ask_user(
            "Please enter the part category's name were you would like the Part's to show up.",
            "plugin-test"
        )

        if part_category is None:
            ui.messageBox("Invalid part category", TITLE)
            return False

        config_text = '\n'.join((
            "[SERVER]",
            "current = default",
            "",
            "[default]",
            f"{config.CFG_ADDRESS} = {address}",
            f"{config.CFG_TOKEN} = {token}",
            f"{config.CFG_PART_CATEGORY} = {part_category}",         
        ))

        with open(config_path, "w") as f:
            f.write(config_text)

    try:
        config_dict = configparser.ConfigParser()
        config_dict.read(config_path)
        config.CONFIG = config_dict
    except: 
        return False

    return True


def config_get(ref):
    """ returns current config """
    # SET where config is saved here
    crt_srv = config.CONFIG['SERVER']['current']  # ref enables multiple server confs

    if ref == 'srv_address':
        return config.CONFIG[crt_srv][config.CFG_ADDRESS]
    if ref == 'srv_token':
        return config.CONFIG[crt_srv][config.CFG_TOKEN]
    if ref == config.CFG_PART_CATEGORY:
        return config.CONFIG[crt_srv][config.CFG_PART_CATEGORY]
    if ref == config.CFG_TEMPLATE_PARAMETER:
        return config.CONFIG[crt_srv][config.CFG_TEMPLATE_PARAMETER]

    raise NotImplementedError('unknown ref')


@apper.lib_import(config.lib_path)
def config_ref(ref):
    """ retuns a (cached) api-object based on ref """
    from inventree.base import ParameterTemplate
    from inventree.part import PartCategory

    def get(ref, cat):
        """ handles caching of ref-objects """
        if config.REF_CACHE.get(ref):
            return config.REF_CACHE.get(ref)

        ref_vals = [category for category in cat.list(inv_api()) if category.name == config_get(ref)]
        if ref_vals:
            config.REF_CACHE[ref] = ref_vals[0]
            return config.REF_CACHE[ref]
        return None

    # set the API-objects
    if ref == config.CFG_PART_CATEGORY:
        return get(ref, PartCategory)
    if ref == config.CFG_TEMPLATE_PARAMETER:
        return get(ref, ParameterTemplate)

    raise NotImplementedError('unknown ref')
# endregion


# region API
@apper.lib_import(config.lib_path)
def inv_api():
    """ connect to API """
    from inventree.api import InvenTreeAPI

    if not config.INV_API:
        config.INV_API = InvenTreeAPI(config_get('srv_address'), token=config_get('srv_token'))
        return config.INV_API
    return config.INV_API


@apper.lib_import(config.lib_path)
def inventree_get_part(part_id):
    """ returns a part from InvenTree """
    from inventree.part import Part
    from inventree.base import Parameter

    def search(parameters, part_id):
        try:
            part = [a.part for a in parameters if a._data['data'] == part_id]
            if len(part) == 1:
                return Part(inv_api(), part[0])
            return False
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise Exception from _e

    parameters = Parameter.list(inv_api())
    if not parameters:
        parameters = []
    if type(part_id) in (list, tuple):
        result = {}
        for cur_id in part_id:
            result[cur_id] = search(parameters, cur_id)
        return result
    return search(parameters, part_id)
# endregion


# region bom functions
def extract_bom():
    """ returns bom """
    try:
        ao = apper.AppObjects()
        design = ao.product
        if not design:
            ao.ui.messageBox('No active design', 'Extract BOM')
            return []

        # Get all occurrences in the root component of the active design
        occs = design.rootComponent.allOccurrences

        # Gather information about each unique component
        bom = []
        for occ in occs:
            comp = occ.component
            already_exists = False

            # Go through the BOM for items previously added 
            for item in bom:
                if item['component'] == comp:
                    # Increment the instance count of the existing row.
                    item['instances'] += 1
                    already_exists = True
                    break

            if already_exists is False:
                # Gather any BOM worthy values from the component
                volume = 0
                bodies = comp.bRepBodies
                for bodyK in bodies:
                    if bodyK.isSolid:
                        volume += bodyK.volume

                # Add this component to the BOM
                node = component_info(comp, comp_set=True)
                node['volume'] = volume
                node['linked'] = occ.isReferencedComponent
                bom.append(node)

        bom_parts = inventree_get_part([item['id'] for item in bom])
        for item in bom:
            part = bom_parts[item['id']]

            if part is not False:
                item['synced'] = True # "<span style='color: green;'> Synced </span>"
            else:
                item['synced'] = False # "<span style='color: red;'> Not synced </span>"

        # Display the BOM
        return bom
    except Exception as _e:
        config.app_tracking.capture_exception(_e)
        raise _e


def component_info(comp, parent='#', comp_set=False):
    """ returns a node element """
    node = {
        'name': comp.name,
        'IPN': comp.partNumber,
        'id': comp.id,
        'revision-id': comp.revisionId,
        'instances': 1,
        'parent': parent,
    }

    if comp_set:
        node['component'] = comp
    else:
        node['state'] = {'opened': True, 'checkbox_disabled': False}
        node["type"] = "4-root_component"
        node["text"] = comp.name

    return node


def make_component_tree():
    """ generates the full tree """
    ao = apper.AppObjects()
    root = ao.root_comp

    node_list = []

    root_node = component_info(root)
    node_list.append(root_node)

    if root.occurrences.count > 0:
        make_assembly_nodes(root.occurrences, node_list, root.id)

    return node_list


def make_assembly_nodes(occurrences: adsk.fusion.OccurrenceList, node_list, parent):
    """ adds one node and checks for others """
    for occurrence in occurrences:

        node = component_info(occurrence.component, parent)
        if occurrence.childOccurrences.count > 0:

            node["type"] = "4-component_group"
            node_list.append(node)
            make_assembly_nodes(occurrence.childOccurrences, node_list, occurrence.component.id)

        else:
            node["type"] = "4-component"
            node_list.append(node)
# endregion
