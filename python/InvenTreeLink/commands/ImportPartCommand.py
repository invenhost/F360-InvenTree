import adsk.core
import adsk.fusion
import adsk.cam

import os
from datetime import datetime

from ..apper import apper
from .. import functions
from .. import helpers
from .. import config


class ImportPartCommand(apper.Fusion360CommandBase):

    @apper.lib_import(config.lib_path)
    def on_execute(self, command: adsk.core.Command, command_inputs: adsk.core.CommandInputs, args, input_values):
        try:
            ao = apper.AppObjects()

        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
