""" InveTree addin for Autodesk Fusion360 """
# Author-Matthias MAIR<mjmair DOT com>
# Description-use InvenTree-Inventory

import unicodedata
import re


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


import configparser
import json
import os
import sys
import traceback

from datetime import datetime
from enum import Enum

import adsk.cam
import adsk.core
import adsk.fusion

# Add in Modules Path
sys.path.insert(0, str(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Modules')))
from inventree.api import InvenTreeAPI
from inventree.base import Parameter, ParameterTemplate
from inventree.part import Part, PartCategory, PartAttachment

import sentry_sdk


# global variables for handling the addin-aspects
_APP = adsk.core.Application.cast(None)
_APP_UI = adsk.core.UserInterface.cast(None)
_APP_PANEL = None  # Holds reference for the newly added Panel
_APP_BTN_LST = []  # all added buttons for easy reference # debug
_APP_HANDLERS = []  # all handlers as per ADESK-recommandation

# globals to hold objects
BOM = []  # BOM-List
BOM_HIR = []  # Hirarchical BOM
INV_API = None  # API-connection
CONFIG = {}  # Config section
REF_CACHE = {}  # saves refs for reduced loading

# Magic numbers
ITEM_PALETTE = 'InvenTreePalette'

CFG_ADDRESS = 'address'
CFG_TOKEN = 'token'
CFG_TEMPLATE_PARAMETER = 'parameter_template_name'
CFG_PART_CATEGORY = 'part_category'

DEF_SHOW_PALETTE = "ShowPalette"
DEF_SEND_BOM = "SendBom"
DEF_SEND_ONLINE_STATE = "SendOnlineState"
DEF_SEND_PART = "SendPart"
DEF_SEND_STEP = "SendStep"

VERSION = 'InvenTreeLink@0.1'

# setup sentry
sentry_sdk.init(
    "https://8b2c118182cd4d43bd6efe3f211b9595@o1047628.ingest.sentry.io/6024677",
    traces_sample_rate=1.0,
    release=VERSION,
)


class Fusion360Template:
    SEPARATOR = ":"
    # Base parameter name
    BASE = "Fusion360" + SEPARATOR
    # Bounding box
    BOUNDING_BOX_BASE = BASE + "BoundingBox" + SEPARATOR

    def __init__(self, name, unit=None):
        self.name = name
        self.unit = unit

    def create_template(self):
        ParameterTemplate.create(inv_api(), {
            "name": self.name,
            "units": self.unit or ""
        })

    def create_parameter(self, part, data):
        Parameter.create(inv_api(), {'part': part.pk, 'template': self.pk, 'data': data})

    def update_parameter(self, part, data):
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


# region functions
def config_get(ref):
    """ returns current config """
    # SET where config is saved here
    crt_srv = CONFIG['SERVER']['current']  # ref enables multiple server confs

    if ref == 'srv_address':
        return CONFIG[crt_srv][CFG_ADDRESS]
    if ref == 'srv_token':
        return CONFIG[crt_srv][CFG_TOKEN]
    if ref == CFG_PART_CATEGORY:
        return CONFIG[crt_srv][CFG_PART_CATEGORY]
    if ref == CFG_TEMPLATE_PARAMETER:
        return CONFIG[crt_srv][CFG_TEMPLATE_PARAMETER]

    raise NotImplementedError('unknown ref')


def config_ref(ref):
    """ retuns a (cached) api-object based on ref """
    def get(ref, cat):
        """ handles caching of ref-objects """
        global REF_CACHE
        if REF_CACHE.get(ref):
            return REF_CACHE.get(ref)

        ref_vals = [category for category in cat.list(inv_api()) if category.name == config_get(ref)]
        if ref_vals:
            REF_CACHE[ref] = ref_vals[0]
            return REF_CACHE[ref]
        return None

    # set the API-objects
    if ref == CFG_PART_CATEGORY:
        return get(ref, PartCategory)
    if ref == CFG_TEMPLATE_PARAMETER:
        return get(ref, ParameterTemplate)

    raise NotImplementedError('unknown ref')


def error(typ_str=None):
    """ shows message box when error raised """
    # generate error message
    if typ_str == 'cmd':
        ret_msg = 'Command executed failed: {}'.format(traceback.format_exc())
    else:
        ret_msg = 'Failed:\n{}'.format(traceback.format_exc())

    # show message
    if _APP_UI:
        _APP_UI.messageBox(ret_msg)
    else:
        print(ret_msg)


# Components
def _extract_bom():
    """ returns bom """
    try:
        design = _APP.activeProduct
        if not design:
            _APP_UI.messageBox('No active design', 'Extract BOM')
            return []

        # Get all occurrences in the root component of the active design
        occs = design.rootComponent.allOccurrences

        # Gather information about each unique component
        bom = []
        for occ in occs:
            comp = occ.component
            jj = 0
            for bomI in bom:
                if bomI['component'] == comp:
                    # Increment the instance count of the existing row.
                    bomI['instances'] += 1
                    break
                jj += 1

            if jj == len(bom):
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

        # Display the BOM
        return bom
    except Exception as _e:
        sentry_sdk.capture_exception(_e)
        raise _e


def component_info(comp, parent='#', comp_set=False):
    """ returns a node element """
    node = {
        'name': comp.name,
        'nbr': comp.partNumber,
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
    root = _APP.activeProduct.rootComponent

    node_list = []

    root_node = component_info(root)
    root_node["type"] = "4-root_component"
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


# API
def inv_api():
    """ connect to API """
    global INV_API
    if not INV_API:
        INV_API = InvenTreeAPI(config_get('srv_address'), token=config_get('srv_token'))
        return INV_API
    return INV_API


def inventree_get_part(part_id):
    """ returns a part from InvenTree """
    def search(parameters, part_id):
        try:
            part = [a.part for a in parameters if a._data['data'] == part_id]
            if len(part) == 1:
                return Part(inv_api(), part[0])
            return False
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
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


# region handlers
# Event handler for the commandExecuted event.
class ShowPaletteCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            # Create and display the palette.
            palette = _APP_UI.palettes.itemById(ITEM_PALETTE)
            if not palette:
                palette = _APP_UI.palettes.add(ITEM_PALETTE, 'InvenTreeLink', 'palette.html', True, True, True, 300, 200)

                # Dock the palette to the right side of Fusion window.
                palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

                # Add handler to HTMLEvent of the palette.
                onHTMLEvent = HTMLEventHandler()
                palette.incomingFromHTML.add(onHTMLEvent)
                _APP_HANDLERS.append(onHTMLEvent)

                # Add handler to CloseEvent of the palette.
                onClosed = MyCloseEventHandler()
                palette.closed.add(onClosed)
                _APP_HANDLERS.append(onClosed)
            else:
                palette.isVisible = True
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error('cmd')


# Event handler for the commandCreated event.
class ShowPaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            command = args.command
            onExecute = ShowPaletteCommandExecuteHandler()
            command.execute.add(onExecute)
            _APP_HANDLERS.append(onExecute)
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the commandExecuted event.
class SendBomCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            palette = _APP_UI.palettes.itemById(ITEM_PALETTE)
            if palette:
                palette.sendInfoToHTML(DEF_SEND_BOM, '<br><br><br><div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>')

                global BOM, BOM_HIR
                start = datetime.now()
                BOM = _extract_bom()
                BOM_HIR = make_component_tree()
                body = ''.join(['<tr><td>%s</td><td>%s</td></tr>' % (a['name'], a['instances']) for a in BOM])
                table_c = '<div class="overflow-auto"><table class="table table-sm table-striped table-hover"><thead><tr><th scope="col">Name</th><th scope="col">Count</th></tr></thead><tbody>{body}</tbody></table></div>'.format(body=body)

                palette.sendInfoToHTML(DEF_SEND_BOM, '<p>{nbr} parts found in {time}</p>{table}'.format(nbr=len(BOM), table=table_c, time=datetime.now() - start))
                palette.sendInfoToHTML('sendTree', json.dumps(BOM_HIR))
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error('cmd')


# Event handler for the commandCreated event.
class SendBomCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            command = args.command
            onExecute = SendBomCommandExecuteHandler()
            command.execute.add(onExecute)
            _APP_HANDLERS.append(onExecute)
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the commandExecuted event.
class SendBomOnlineCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            palette = _APP_UI.palettes.itemById(ITEM_PALETTE)
            if palette:
                palette.sendInfoToHTML(DEF_SEND_BOM, '<br><br><br><div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>')

                # Work with it
                global BOM
                inv_status = inventree_get_part([a['id'] for a in BOM])
                for a in BOM:
                    a['status'] = inv_status[a['id']]

                body = ''.join(['<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (a['name'], a['instances'], a['status']) for a in BOM])
                table = '<div class="overflow-auto"><table class="table table-sm table-striped table-hover"><thead><tr><th scope="col">Name</th><th scope="col">Count</th><th scope="col">Is InvenTree</th></tr></thead><tbody>{body}</tbody></table></div>'.format(body=body)

                palette.sendInfoToHTML(DEF_SEND_BOM, '{table}'.format(table=table))
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error('cmd')


# Event handler for the commandCreated event.
class SendBomOnlineCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            command = args.command
            onExecute = SendBomOnlineCommandExecuteHandler()
            command.execute.add(onExecute)
            _APP_HANDLERS.append(onExecute)
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the commandExecuted event.
class SendShowPartCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            if _APP_UI.activeSelections.count == 1:
                occ = adsk.fusion.Occurrence.cast(_APP_UI.activeSelections[0].entity)
                inp = args.command.commandInputs
                part = inventree_get_part(occ.component.id)

                def getText(text_name, obj, item, data):
                    # get value
                    value = inp.itemById(text_name).text
                    # compare
                    if not getattr(obj, item) == value:
                        data[item] = value

                def getValue(text_name, obj, item, data):
                    value = inp.itemById(text_name).value
                    # compare
                    if not getattr(obj, item) == value:
                        data[item] = value

                if part:
                    _data = {}
                    getText('text_part_name', part, 'name', _data)
                    getText('text_part_ipn', part, 'IPN', _data)
                    getText('text_part_description', part, 'description', _data)
                    getText('text_part_notes', part, 'notes', _data)
                    getText('text_part_keywords', part, 'keywords', _data)
                    getValue('bool_part_virtual', part, 'virtual', _data)
                    getValue('bool_part_template', part, 'is_template', _data)
                    getValue('bool_part_assembly', part, 'assembly', _data)
                    getValue('bool_part_component', part, 'component', _data)
                    getValue('bool_part_trackable', part, 'trackable', _data)
                    getValue('bool_part_purchaseable', part, 'purchaseable', _data)
                    getValue('bool_part_salable', part, 'salable', _data)

                    part.save(_data)
                else:
                    sentry_sdk.capture_message('part not found by reference', 'fatal')
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error('cmd')


class ShowPartChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            eventArgs = adsk.core.InputChangedEventArgs.cast(args)
            if _APP_UI.activeSelections.count == 1:
                occ = adsk.fusion.Occurrence.cast(_APP_UI.activeSelections[0].entity)
                arg_id = eventArgs.input.id
                inp = eventArgs.inputs.command.commandInputs

                # Check to see what button was used
                if arg_id in ('partSelection', 'button_refresh'):
                    self.part_refresh(occ, inp, inventree_get_part(occ.component.id))
                elif arg_id == 'button_create':
                    # make part
                    part = self.part_create(occ, config_ref(CFG_PART_CATEGORY))
                    # refresh display
                    self.part_refresh(occ, inp, part)
                elif arg_id == 'APITabBar':
                    pass
                else:
                    print('not found')
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()

    def part_create(self, occ, cat):
        """ create part based on occurence """
        # build up args
        part_kargs = {
            'name': occ.component.name,
            'description': occ.component.description if occ.component.description else 'None',
            'IPN': occ.component.partNumber,
            'active': True,
            'virtual': False,
        }
        # add category if set
        if cat:
            part_kargs.update({'category': cat.pk})
        # create part itself
        part = Part.create(inv_api(), part_kargs)
        # check if part created - else raise error
        if not part:
            _APP_UI.messageBox('Error occured during API-call')
            return
        elif not part.pk:
            error_detail = [f'<strong>{a}</strong>\n{b[0]}' for a, b in part._data.items()]
            _APP_UI.messageBox(f'Error occured:<br><br>{"<br>".join(error_detail)}')
            return

        Fusion360Parameters.ID.value.create_parameter(part, occ.component.id)
        Fusion360Parameters.AREA.value.create_parameter(part, occ.physicalProperties.area)
        Fusion360Parameters.VOLUME.value.create_parameter(part, occ.physicalProperties.volume)
        Fusion360Parameters.MASS.value.create_parameter(part, occ.physicalProperties.mass)
        Fusion360Parameters.DENSITY.value.create_parameter(part, occ.physicalProperties.density)

        if occ.component.material.name:
            Fusion360Parameters.MATERIAL.value.create_parameter(part, occ.component.material.name)

        axis = ['x', 'y', 'z']
        bb_min = {a: getattr(occ.boundingBox.minPoint, a) for a in axis}
        bb_max = {a: getattr(occ.boundingBox.maxPoint, a) for a in axis}
        bb = {a: bb_max[a] - bb_min[a] for a in axis}

        Fusion360Parameters.BOUNDING_BOX_WIDTH.value.create_parameter(part, bb["x"])
        Fusion360Parameters.BOUNDING_BOX_HEIGHT.value.create_parameter(part, bb["y"])
        Fusion360Parameters.BOUNDING_BOX_DEPTH.value.create_parameter(part, bb["z"])

        return part

    def part_refresh(self, occ, inp, part):
        """ updates PartInfo command-inputs with values for supplied parts """
        unitsMgr = _APP.activeDocument.design.unitsManager

        def setText(text_name, item):
            value = item if item else ''
            inp.itemById(text_name).text = str(value)

        def setFormatValue(text_name, item, format_string, display_unit=None, display_format=True):
            if not display_unit:
                display_unit = ''
            else:
                display_format = False
            if str(item) == 'nan':
                item = 0
            value = format_string % float(unitsMgr.formatInternalValue(item, display_unit, display_format))
            setText(text_name, value)

        # Compnent Infos
        setText('text_id', occ.component.id)
        setText('text_name', occ.component.name)
        setText('text_description', occ.component.description)
        setText('text_opacity', occ.component.opacity)
        setText('text_partNumber', occ.component.partNumber)

        # Physics
        setFormatValue('text_area', occ.physicalProperties.area, '%.3f cm2')
        setFormatValue('text_volume', occ.physicalProperties.volume, '%.3f cm3')
        setFormatValue('text_mass', occ.physicalProperties.mass, '%.3f g', 'g')
        setFormatValue('text_density', occ.physicalProperties.density, '%.3f g/cm3', 'g/cm/cm/cm')
        setText('text_material', occ.component.material.name if occ.component.material else '')

        # bounding box
        axis = ['x', 'y', 'z']
        bb_min = {a: getattr(occ.boundingBox.minPoint, a) for a in axis}
        bb_max = {a: getattr(occ.boundingBox.maxPoint, a) for a in axis}
        bb = {a: bb_max[a] - bb_min[a] for a in axis}

        tableInput = inp.itemById('table')
        tableInput.clear()
        tbl_cmds = tableInput.commandInputs
        tbl_val = [bb, bb_min, bb_max]
        tbl_col = ['bound', 'bound_min', 'bound_max']
        for i in range(3):
            row = tableInput.rowCount
            for ii in range(4):
                if ii == 0:
                    val = tbl_col[i]
                else:
                    val = '%s: %.3f' % (axis[ii - 1], tbl_val[i][axis[ii - 1]])
                ref = '%s_%s' % (i, ii)
                txtinp = tbl_cmds.addTextBoxCommandInput('table_' + ref, ref, val, 1, True)
                tableInput.addCommandInput(txtinp, row, ii)

        # InvenTree part
        if part:
            if part.thumbnail:  # TODO implement images
                pass
            #     inp.itemById('text_part_image').imageFile = part.thumbnail
            #     inp.itemById('text_part_image').isVisible = True
            setText('text_part_name', part.name)
            setText('text_part_ipn', part.IPN)
            setText('text_part_description', part.description)
            setText('text_part_notes', part.notes)
            setText('text_part_keywords', part.keywords)
            setText('text_part_category', part.getCategory().pathstring)
            # setText('text_part_stock', part.in_stock)  # TODO fix
            inp.itemById('bool_part_virtual').value = part.virtual
            inp.itemById('bool_part_template').value = part.is_template
            inp.itemById('bool_part_assembly').value = part.assembly
            inp.itemById('bool_part_component').value = part.component
            inp.itemById('bool_part_trackable').value = part.trackable
            inp.itemById('bool_part_purchaseable').value = part.purchaseable
            inp.itemById('bool_part_salable').value = part.salable
            setText('text_part_bom', part.name)
            # setText('text_part_suppliers', part.suppliers)  # TODO fix
            part_url = inv_api().base_url + part._url
            message = '<div align="center">open <b>part %s</b> in <b>%s</b> <a href="%s">with this link</a>.</div>' % (part.pk, inv_api().server_details['instance'], part_url)
            inp.itemById('text_part_link').formattedText = message
            if part.link:
                inp.itemById('text_part_link_ext').formattedText = '<a href="%s">external link</a>' % part.link
            else:
                inp.itemById('text_part_link_ext').isVisible = False

        # Control visibility of Groups
        inp.itemById('grp_1').isVisible = bool(part)
        inp.itemById('grp_2').isVisible = bool(part)
        inp.itemById('grp_3').isVisible = bool(part)
        inp.itemById('button_create').isVisible = not bool(part)


# Event handler for the commandCreated event.
class SendShowPartCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            command = args.command
            onExecute = SendShowPartCommandExecuteHandler()
            command.execute.add(onExecute)
            _APP_HANDLERS.append(onExecute)

            onInputChanged = ShowPartChangedHandler()
            command.inputChanged.add(onInputChanged)
            _APP_HANDLERS.append(onInputChanged)

            inputs = command.commandInputs

            # Tabs
            tabCmdInput1 = inputs.addTabCommandInput('tab_1', 'Start')
            tab1ChildInputs = tabCmdInput1.children
            tabCmdInput2 = inputs.addTabCommandInput('tab_2', 'Teil-Details')
            tab2ChildInputs = tabCmdInput2.children

            # TextInputs for general information
            tab2ChildInputs.addTextBoxCommandInput('text_id', 'id', 'id', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_name', 'name', 'name', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_description', 'description', 'description', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_opacity', 'opacity', 'opacity', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_partNumber', 'partNumber', 'partNumber', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_area', 'area', 'area', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_volume', 'volume', 'volume', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_mass', 'mass', 'mass', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_density', 'density', 'density', 1, True)
            tab2ChildInputs.addTextBoxCommandInput('text_material', 'material', 'material', 1, True)
            tableInput = tab2ChildInputs.addTableCommandInput('table', 'Table', 4, '1:1:1:1')
            tableInput.isFullWidth = True
            tableInput.tablePresentationStyle = 2

            # Select
            selectInput = tab1ChildInputs.addSelectionInput('partSelection', 'Select', 'Please select components')
            selectInput.addSelectionFilter('Occurrences')
            selectInput.setSelectionLimits(1, 1)
            # Buttons
            tab1ChildInputs.addBoolValueInput('button_create', 'create part', False, 'resources/ButtonCreate', True)
            tab1ChildInputs.addBoolValueInput('button_refresh', 'refresh Information', False, 'resources/SendOnlineState', True)

            # TextInputs for InvenTree
            grpCmdInput1 = tab1ChildInputs.addGroupCommandInput('grp_1', 'General')
            grp1ChildInputs = grpCmdInput1.children
            img = tab1ChildInputs.addImageCommandInput('text_part_image', 'image', 'resources/blank_image.png')
            img.isVisible = False
            grp1ChildInputs.addTextBoxCommandInput('text_part_name', 'name', 'name', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_ipn', 'IPN', 'IPN', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_description', 'description', 'description', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_notes', 'note', 'note', 2, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_keywords', 'keywords', 'keywords', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_category', 'category', 'category', 1, True)
            grp1ChildInputs.addTextBoxCommandInput('text_part_link', '', 'linktext', 1, True)

            grpCmdInput2 = tab1ChildInputs.addGroupCommandInput('grp_2', 'Settings')
            grp2ChildInputs = grpCmdInput2.children
            grp2ChildInputs.addBoolValueInput('bool_part_virtual', 'virtual', True)
            grp2ChildInputs.addBoolValueInput('bool_part_template', 'template', True)
            grp2ChildInputs.addBoolValueInput('bool_part_assembly', 'assembly', True)
            grp2ChildInputs.addBoolValueInput('bool_part_component', 'component', True)
            grp2ChildInputs.addBoolValueInput('bool_part_trackable', 'trackable', True)
            grp2ChildInputs.addBoolValueInput('bool_part_purchaseable', 'purchaseable', True)
            grp2ChildInputs.addBoolValueInput('bool_part_salable', 'salable', True)

            grpCmdInput3 = tab1ChildInputs.addGroupCommandInput('grp_3', 'Supply')
            grp3ChildInputs = grpCmdInput3.children
            # grp3ChildInputs.addTextBoxCommandInput('text_part_stock', 'stock', 'stock', 1, True)  # TODO fix
            grp3ChildInputs.addTextBoxCommandInput('text_part_bom', 'BOM items', 'Bom items', 1, True)
            # grp3ChildInputs.addTextBoxCommandInput('text_part_suppliers', 'suppliers', 'suppliers', 1, True)  # TODO fix
            grp3ChildInputs.addTextBoxCommandInput('text_part_link_ext', 'link', '', 1, True)

            # Turn off everything InvenTree
            inputs.itemById('grp_1').isVisible = False
            inputs.itemById('grp_2').isVisible = False
            inputs.itemById('grp_3').isVisible = False
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the palette close event.
class MyCloseEventHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            pass  # TODO cleanup function needed?
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the palette HTML event.
class HTMLEventHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            htmlArgs = adsk.core.HTMLEventArgs.cast(args)
            data = json.loads(htmlArgs.data)

            palette = _APP_UI.palettes.itemById(ITEM_PALETTE)
            if htmlArgs.action == 'getBom':
                if palette:
                    _APP_UI.commandDefinitions.itemById(DEF_SEND_BOM).execute()

            elif htmlArgs.action == 'getBomOnline':
                if palette:
                    _APP_UI.commandDefinitions.itemById(DEF_SEND_ONLINE_STATE).execute()

            elif htmlArgs.action == 'showPart':
                selections = _APP_UI.activeSelections
                selections.clear()

                design = _APP.activeDocument.design
                cmp = _APP.activeProduct.allComponents.itemById(data['id'])
                # occ = design.rootComponent.allOccurrencesByComponent(cmp)
                # bb = [a for a in design.rootComponent.allOccurrences if a.name == cmp.name]
                token = cmp.entityToken
                entitiesByToken = design.findEntityByToken(token)
                selections.add(entitiesByToken)  # TODO selection not working
                print(data['id'])
                _APP_UI.commandDefinitions.itemById(DEF_SEND_PART).execute()

            else:
                raise NotImplementedError('unknown message received from HTML')
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the commandCreated event.
class SendStepCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            command = args.command
            onExecute = SendStepCommandExecuteHandler()
            command.execute.add(onExecute)
            _APP_HANDLERS.append(onExecute)
        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error()


# Event handler for the commandExecuted event.
class SendStepCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """ generic function - called when handler called """
        try:
            _APP_UI.messageBox("STEP FILE")

            if _APP_UI.activeSelections.count == 1:
                occ = adsk.fusion.Occurrence.cast(_APP_UI.activeSelections[0].entity)

                file_name = "{}.step".format(slugify(occ.component.name))

                temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.temp_export')
                if os.path.isdir(temp_dir) is False:
                    os.makedirs(temp_dir)

                temp_path = os.path.join(temp_dir, file_name)

                self._write_step(temp_path, occ.component)

                _APP_UI.messageBox("File at {}, size: {}".format(temp_path, os.path.getsize(temp_path)))

                part = inventree_get_part(occ.component.id)

                if part is False:
                    _APP_UI.messageBox("Part is not synced with InvenTree yet")
                else:
                    if PartAttachment.upload_attachment(
                        inv_api(),
                        part.pk,
                        attachment=temp_path,
                        comment="STEP file generated by InvenTreeLink on {}, revision {}".format(datetime.now(), occ.component.revisionId)
                    ) is False:
                        _APP_UI.messageBox("Failed to upload!")
                    else:
                        _APP_UI.messageBox("Succesfully attached STEP file to Part {}".format(part.pk))

                os.remove(temp_path)

            else:
                _APP_UI.messageBox("Wrong number of entities selected: {}".format(_APP_UI.activeSelections.count))

        except Exception as _e:
            sentry_sdk.capture_exception(_e)
            error('cmd')

    def _write_step(self, output_path, component: adsk.fusion.Component):
        file_path = output_path
        if os.path.exists(file_path):
            print("Step file \"{}\" already exists".format(file_path))
            return

        print("Writing step file \"{}\"".format(file_path))
        export_manager = component.parentDesign.exportManager

        options = export_manager.createSTEPExportOptions(output_path, component)

        if export_manager.execute(options) is False:
            _APP_UI.messageBox("Failed to export STEP")

# endregion


def run(context):
    """ generic function - called when addin starts up """
    try:
        global _APP_UI, _APP, _APP_PANEL, _APP_BTN_LST
        _APP = adsk.core.Application.get()
        _APP_UI = _APP.userInterface

        # Make UI
        workSpace = _APP_UI.workspaces.itemById('FusionSolidEnvironment')
        tbPanels = workSpace.toolbarPanels
        _APP_PANEL = tbPanels.itemById('InvenTreeLink')
        if _APP_PANEL:
            _APP_PANEL.deleteMe()
        _APP_PANEL = tbPanels.add('InvenTreeLink', 'InvenTree - Link', 'SelectPanel', False)

        print("Added Panel")

        # Add a command that displays the panel.
        showPaletteCmdDef = _APP_UI.commandDefinitions.itemById(DEF_SHOW_PALETTE)
        if not showPaletteCmdDef:
            showPaletteCmdDef = _APP_UI.commandDefinitions.addButtonDefinition(DEF_SHOW_PALETTE, 'Show BOM overview', 'Show the BOM overview palette.', 'resources\\ShowPalette')

            # Connect to Command Created event.
            onCommandCreated = ShowPaletteCommandCreatedHandler()
            showPaletteCmdDef.commandCreated.add(onCommandCreated)
            _APP_HANDLERS.append(onCommandCreated)
            _APP_BTN_LST.append([DEF_SHOW_PALETTE, showPaletteCmdDef])

        SendBomCmdDef = _APP_UI.commandDefinitions.itemById(DEF_SEND_BOM)
        if not SendBomCmdDef:
            SendBomCmdDef = _APP_UI.commandDefinitions.addButtonDefinition(DEF_SEND_BOM, 'Load BOM for assembly', 'Load the BOM for the assembly in the current file.', 'resources\\SendBom')
            SendBomCmdDef.isPromotedByDefault = True
            SendBomCmdDef.isPromoted = True

            # Connect to Command Created event.
            onCommandCreated = SendBomCommandCreatedHandler()
            SendBomCmdDef.commandCreated.add(onCommandCreated)
            _APP_HANDLERS.append(onCommandCreated)
            _APP_BTN_LST.append([DEF_SEND_BOM, SendBomCmdDef])

        SendBomOnlineCmdDef = _APP_UI.commandDefinitions.itemById(DEF_SEND_ONLINE_STATE)
        if not SendBomOnlineCmdDef:
            SendBomOnlineCmdDef = _APP_UI.commandDefinitions.addButtonDefinition(DEF_SEND_ONLINE_STATE, 'Get InvenTree Information', 'Fetch the InvenTree information for all BOM-parts.', 'resources\\SendOnlineState')

            # Connect to Command Created event.
            onCommandCreated = SendBomOnlineCommandCreatedHandler()
            SendBomOnlineCmdDef.commandCreated.add(onCommandCreated)
            _APP_HANDLERS.append(onCommandCreated)
            _APP_BTN_LST.append([DEF_SEND_ONLINE_STATE, SendBomOnlineCmdDef])

        SendShowPartCmdDef = _APP_UI.commandDefinitions.itemById(DEF_SEND_PART)
        if not SendShowPartCmdDef:
            SendShowPartCmdDef = _APP_UI.commandDefinitions.addButtonDefinition(
                DEF_SEND_PART,
                'Show part details',
                'Show the InvenTree part-details for the selected part.',
                'resources\\SendPart'
            )

            SendShowPartCmdDef.isPromotedByDefault = True
            SendShowPartCmdDef.isPromoted = True

            # Connect to Command Created event.
            onCommandCreated = SendShowPartCommandCreatedHandler()
            SendShowPartCmdDef.commandCreated.add(onCommandCreated)
            _APP_HANDLERS.append(onCommandCreated)
            _APP_BTN_LST.append([DEF_SEND_PART, SendShowPartCmdDef])

        SendStepCmdDef = _APP_UI.commandDefinitions.itemById(DEF_SEND_STEP)
        if not SendStepCmdDef:
            SendStepCmdDef = _APP_UI.commandDefinitions.addButtonDefinition(
                DEF_SEND_STEP,
                'Upload STEP to attachments',
                'Generates a STEP file and attaches it to a part.',
                'resources\\SendBom'
            )

            SendStepCmdDef.isPromotedByDefault = True
            SendStepCmdDef.isPromoted = True

            # Connect to Command Created event.
            onCommandCreated = SendStepCommandCreatedHandler()
            SendStepCmdDef.commandCreated.add(onCommandCreated)
            _APP_HANDLERS.append(onCommandCreated)
            _APP_BTN_LST.append([DEF_SEND_STEP, SendStepCmdDef])

        # Add the command to the toolbar.
        for btn in _APP_BTN_LST:
            cntrl = _APP_PANEL.controls.itemById(btn[0])
            if not cntrl:
                _APP_PANEL.controls.addCommand(btn[1])

        # Load settings
        global CONFIG

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        CONFIG = config

        existing = [parameter.name for parameter in ParameterTemplate.list(inv_api())]
        for variant in Fusion360Parameters:
            template = variant.value

            if template.name in existing:
                continue

            template.create_template()
            print("Created non-existing parameter template " + template.name)

        Fusion360Template.cache_part_templates(ParameterTemplate.list(inv_api()))

        # with open('conf.ini', 'w') as configfile:
        #     config.write(configfile)
    except Exception as _e:
        sentry_sdk.capture_exception(_e)
        error()


def stop(context):
    """ generic function - called when addin stopped """
    global _APP_BTN_LST
    try:
        # Delete the palette created by this add-in.
        palette = _APP_UI.palettes.itemById(ITEM_PALETTE)
        if palette:
            palette.deleteMe()

        for btn in _APP_BTN_LST:
            cntrl = _APP_PANEL.controls.itemById(btn[0])
            if cntrl:
                cntrl.deleteMe()
                _APP_BTN_LST.remove(btn)

        if _APP_PANEL:
            _APP_PANEL.deleteMe()
    except Exception as _e:
        sentry_sdk.capture_exception(_e)
        error()
