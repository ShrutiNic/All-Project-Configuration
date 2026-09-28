#!/usr/bin/env python3
'''
Copyright 2024-2025 Accolade Electronics Pvt. Ltd

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License 
version 2 as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

file        main_cli.py
brief       This is the main script file for launching the service tool application

date        12 Nov 2024
author      Accolade Electronics <www.accoladeelectronics.com>

tested on python 3.11.8 on windows 11 x64
d
# dependencies

PCAN drivers must be installed

# run the script to launch app
launch_app.sh
'''
                            
import app_logic

bit_rate = '500Kbps'
tester_id = '0x726'
ecu_id = '0x72E'
iso_tp_addressing_mode = '11B_FIXED_NORMAL'

int_tester_id = int(tester_id, 16)
int_ecu_id = int(ecu_id, 16)
                                    

app_logic.create_gui()

