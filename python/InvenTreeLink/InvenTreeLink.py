import adsk.core
import traceback

import os

try:
    from .apper import apper
    from . import config
    from . import functions

    # Create our addin definition object
    inventreelink = apper.FusionApp(config.app_name, config.company_name, False)
    inventreelink.root_path = config.app_path

    from .commands.EditPartCommand import EditPartCommand
    from .commands.BOMOverviewCommand import BomOverviewCommand
    from .commands.GenerateBomCommand import GenerateBomCommand
    from .commands.UploadStepCommand import UploadStepCommand

    # Commands

    # Palette
    inventreelink.add_command(
        'Show BOM overview',
        BomOverviewCommand,
        {
            'cmd_description': 'Show the BOM overview palette',
            'cmd_id': config.DEF_SHOW_PALETTE,
            'workspace': config.DEF_ENVIROMENT,
            'toolbar_panel_id': config.ToolbarPanelID.MAIN,
            'cmd_resources': 'ShowPalette',
            'command_visible': True,
            'command_promoted': True,
            'palette_id': config.ITEM_PALETTE,
            'palette_name': 'InvenTreeLink BOM overview',
            'palette_html_file_url': os.path.join('commands', 'palette_html', 'palette.html'),
            'palette_use_new_browser': True,
            'palette_is_visible': True,
            'palette_show_close_button': True,
            'palette_is_resizable': True,
            'palette_width': 500,
            'palette_height': 600,
        }
    )

    # Commands that need the palette
    inventreelink.add_command(
        'Load BOM for assembly',
        GenerateBomCommand,
        {
            'cmd_description': 'Load the BOM for the assembly in the current file',
            'cmd_id': config.DEF_GENERATE_BOM,
            'workspace': config.DEF_ENVIROMENT,
            'toolbar_panel_id': config.ToolbarPanelID.MAIN,
            'cmd_resources': config.DEF_GENERATE_BOM,
            'command_visible': True,
            'command_promoted': False,
            'palette_id': config.ITEM_PALETTE,
        }
    )

    inventreelink.add_command(
        'Edit Part',
        EditPartCommand,
        {
            'cmd_description': 'Show the InvenTree part-details for the selected part',
            'cmd_id': config.DEF_EDIT_PART,
            'workspace': config.DEF_ENVIROMENT,
            'toolbar_panel_id': config.ToolbarPanelID.PART,
            'cmd_resources': config.DEF_EDIT_PART,
            'command_visible': True,
            'command_promoted': False,
        }
    )

    inventreelink.add_command(
        'Upload STEP',
        UploadStepCommand,
        {
            'cmd_description': 'Generates a STEP file and attaches it to a part',
            'cmd_id': config.DEF_UPLOAD_STEP,
            'workspace': config.DEF_ENVIROMENT,
            'toolbar_panel_id': config.ToolbarPanelID.PART,
            'cmd_resources': 'ShowPalette',
            'command_visible': True,
            'command_promoted': False,
            'palette_id': config.ITEM_PALETTE,
        }
    )

    app = adsk.core.Application.cast(adsk.core.Application.get())
    ui = app.userInterface


    # Startup up error tracking
    functions.init_sentry()

    # Load config
    if functions.load_config(ui) is False:
        ui.messageBox("Unable to load config.", config.app_name)

    # Ensure templates exsist
    functions.init_Fusion360()

except:  # noqa: E722
    app = adsk.core.Application.get()
    ui = app.userInterface
    if ui:
        ui.messageBox('Initialization of InvenTreeLink Failed: {}'.format(traceback.format_exc()))

debug = True


def run(context):
    """function called on startup"""
    inventreelink.run_app()


def stop(context):
    """function called on stopping"""
    inventreelink.stop_app()
