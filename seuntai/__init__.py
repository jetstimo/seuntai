# -*- coding: utf-8 -*-
# Seuntai - Strand Consolidator - QGIS plugin
# Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version, with the additional terms under section 7 in LICENSE.


def classFactory(iface):  # noqa: N802 - name required by QGIS
    from .plugin import SeuntaiPlugin
    return SeuntaiPlugin(iface)
