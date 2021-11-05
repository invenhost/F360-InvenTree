import adsk.core
import adsk.fusion
import adsk.cam

# Import the entire apper package
from ..apper import apper
from .. import config
from .. import functions
from .. import helpers
from ..functions import Fusion360Parameters


class EditPartCommand(apper.Fusion360CommandBase):
    def on_input_changed(self, command, inputs, changed_input, input_values):
        try:
            ao = apper.AppObjects()
            if ao.ui.activeSelections.count == 1:              
                # TODO: Support Design's

                occ = adsk.fusion.Occurrence.cast(ao.ui.activeSelections[0].entity)
                arg_id = changed_input.id
                inp = inputs.command.commandInputs

                # Check to see what button was used
                if arg_id in ('partSelection', 'button_refresh'):
                    self.part_refresh(occ, inp, functions.inventree_get_part(occ.component.id))
                elif arg_id == 'button_create':
                    # make part
                    part = self.part_create(occ, functions.config_ref(config.CFG_PART_CATEGORY))
                    # refresh display
                    self.part_refresh(occ, inp, part)
                elif arg_id == 'APITabBar':
                    pass
                else:
                    print('not found')
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            helpers.error()

    def on_execute(self, command, inputs, args, input_values):
        try:
            ao = apper.AppObjects()
            if ao.ui.activeSelections.count == 1:
                occ = adsk.fusion.Occurrence.cast(ao.ui.activeSelections[0].entity)
                inp = args.command.commandInputs
                part = functions.inventree_get_part(occ.component.id)

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
                    config.app_tracking.capture_message('part not found by reference', 'fatal')
                    pass
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            pass

    def on_create(self, command, inputs):
        try:
            # Tabs
            tabCmdInput1 = inputs.addTabCommandInput('tab_1', 'Start')
            tab1ChildInputs = tabCmdInput1.children
            part_details_tab = inputs.addTabCommandInput('tab_2', 'Part Details')
            part_details_children = part_details_tab.children

            # TextInputs for general information
            part_details_children.addTextBoxCommandInput('text_id', 'ID', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_name', 'Name', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_description', 'Description', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_opacity', 'Opacity', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_partNumber', 'Part Number', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_area', 'Area', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_volume', 'Volume', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_mass', 'Mass', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_density', 'Density', '', 1, True)
            part_details_children.addTextBoxCommandInput('text_material', 'Material', '', 1, True)
            tableInput = part_details_children.addTableCommandInput('table', 'Table', 4, '1:1:1:1')
            tableInput.isFullWidth = True
            tableInput.tablePresentationStyle = 2

            # Select
            selectInput = tab1ChildInputs.addSelectionInput('partSelection', 'Select', 'Please select components')
            selectInput.addSelectionFilter('Occurrences')
            selectInput.setSelectionLimits(1, 1)
            # Buttons
            tab1ChildInputs.addBoolValueInput('button_create', 'Create part', False, 'commands/resources/ButtonCreate', True)
            tab1ChildInputs.addBoolValueInput('button_refresh', 'Refresh', False, 'commands/resources/SendOnlineState', True)

            # TextInputs for InvenTree
            grpCmdInput1 = tab1ChildInputs.addGroupCommandInput('grp_1', 'General')
            grp1ChildInputs = grpCmdInput1.children
            # img = tab1ChildInputs.addImageCommandInput('text_part_image', 'image', 'blank_image.png')
            # img.isVisible = False  # TODO implement
            grp1ChildInputs.addTextBoxCommandInput('text_part_name', 'Name', '', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_ipn', 'IPN', '', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_description', 'Description', '', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_notes', 'Note', '', 2, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_keywords', 'Keywords', '', 1, False)
            grp1ChildInputs.addTextBoxCommandInput('text_part_category', 'Category', 'category', 1, True)
            grp1ChildInputs.addTextBoxCommandInput('text_part_link', '', 'linktext', 1, True)

            grpCmdInput2 = tab1ChildInputs.addGroupCommandInput('grp_2', 'Settings')
            grp2ChildInputs = grpCmdInput2.children
            grp2ChildInputs.addBoolValueInput('bool_part_virtual', 'Virtual', True)
            grp2ChildInputs.addBoolValueInput('bool_part_template', 'Template', True)
            grp2ChildInputs.addBoolValueInput('bool_part_assembly', 'Assembly', True)
            grp2ChildInputs.addBoolValueInput('bool_part_component', 'Component', True)
            grp2ChildInputs.addBoolValueInput('bool_part_trackable', 'Trackable', True)
            grp2ChildInputs.addBoolValueInput('bool_part_purchaseable', 'Purchasable', True)
            grp2ChildInputs.addBoolValueInput('bool_part_salable', 'Salable', True)

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
            config.app_tracking.capture_exception(_e)
            helpers.error()

    # cstm fnc
    @apper.lib_import(config.lib_path)
    def part_create(self, occ, cat):
        """ create part based on occurence """
        from inventree.part import Part

        ao = apper.AppObjects()

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
        part = Part.create(functions.inv_api(), part_kargs)
        # check if part created - else raise error
        if not part:
            ao.ui.messageBox('Error occured during API-call')
            return
        elif not part.pk:
            error_detail = [f'<strong>{a}</strong>\n{b[0]}' for a, b in part._data.items()]
            ao.ui.messageBox(f'Error occured:<br><br>{"<br>".join(error_detail)}')
            return

        Fusion360Parameters.ID.value.create_parameter(part, occ.component.id)
        Fusion360Parameters.AREA.value.create_parameter(part, occ.physicalProperties.area)
        Fusion360Parameters.VOLUME.value.create_parameter(part, occ.physicalProperties.volume)
        Fusion360Parameters.MASS.value.create_parameter(part, occ.physicalProperties.mass)
        Fusion360Parameters.DENSITY.value.create_parameter(part, occ.physicalProperties.density)

        if occ.component.material and occ.component.material.name:
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
        ao = apper.AppObjects()
        unitsMgr = ao.f_units_manager

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
            part_url = functions.inv_api().base_url + part._url
            message = '<div align="center">open <b>part %s</b> in <b>%s</b> <a href="%s">with this link</a>.</div>' % (part.pk, functions.inv_api().server_details['instance'], part_url)
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
