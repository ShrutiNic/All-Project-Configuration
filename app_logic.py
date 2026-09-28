'''
Copyright 2024-2025 Accolade Electronics Pvt. Ltd

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
version 2 as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

file        app_logic.py
brief       This is the script for handling application logic and background communication

date        22 March 2024
author      Accolade Electronics <www.accoladeelectronics.com>
'''

import app_ui                       # for handling GUI
import app_comm                     # for handling UDS communication and stack
from app_ui import MyApp
import tkinter as tk
from tkinter import filedialog, messagebox
import toml

config = toml.load("config.toml")
#g_ui_main_window = app_ui.create_gui()

############################################## (APP START) ########################################################

def create_gui():
    global app
    root = tk.Tk()
    app = MyApp(root)
    root.mainloop()
 
def connect_to_can_bus(g_config):   
    bit_rate = g_config["bit_rate"]
    tester_id = g_config["tester_id"]  
    ecu_id = g_config["ecu_id"]      
    iso_tp_addressing_mode = g_config["nai_protocol"]
    can_fd = g_config["can_network"]
    ecu_id = hex(ecu_id)
    tester_id = hex(tester_id)

    print("ECU ID, tester ID", ecu_id, tester_id)
    if app_comm.can_init(can_fd, bit_rate, tester_id, ecu_id, iso_tp_addressing_mode):
    # if app_comm.can_init(can_fd, bit_rate, tester_id, ecu_id, iso_tp_addressing_mode):
        print('g_config',g_config)
        print("Ecu id", ecu_id)
        messagebox.showinfo("Success", "Connected to CAN Bus successfully.")
    else:
        messagebox.showerror("Error", "Failed to connect to CAN Bus. Please check the hardware or settings.")

########################################## (GUI EVENT HANDLING) #####################################################

import os
import threading

def browse_file():
    app_ui.append_log(f'attempting to write VIN')
    app_comm.perform_service_tests
    

    file_path = ''
    file_path = app_ui.browse_file_from_disk()
    if file_path:
        app_ui.append_log(f'selected file {file_path}')
        try:
            app_comm.g_file_path = file_path
            app_comm.g_file_size = os.path.getsize(file_path)
            app_ui.set_btn_enabled('UPLOAD_BTN', True)

        except Exception as e:
            print(f'app_logic : {e}')
            return False


def connect_can(g_config):
    # Load values from config
    # bit_rate = g_config.get("bit_rate", "500Kbps")
    bit_rate = g_config.get("bit_rate", "250Kbps")
    nai_protocol = g_config.get("nai_protocol", "PUDS_MSGPROTOCOL_ISO_15765_2_11B_NORMAL")
    can_network = g_config.get("can_network", "CAN_2_0")

    # Get IDs from config
    tester_id = g_config.get("tester_id")
    ecu_id = g_config.get("ecu_id")

    # Basic validation
    if tester_id is None or ecu_id is None:
        app.show_dialog('Error', 'Tester ID and ECU ID must be provided')
        return

    if tester_id == ecu_id:
        app.show_dialog('Error', 'Tester ID cannot be equal to ECU ID')
        return

    try:
        # Convert to hex strings like '0x7E0'
        if isinstance(tester_id, int):
            tester_id = hex(tester_id)
        elif isinstance(tester_id, str):
            tester_id = hex(int(tester_id.strip(), 16))

        if isinstance(ecu_id, int):
            ecu_id = hex(ecu_id)
        elif isinstance(ecu_id, str):
            ecu_id = hex(int(ecu_id.strip(), 16))

    except ValueError:
        app.show_dialog('Error', 'Tester ID or ECU ID is not a valid hexadecimal value')
        return

    print("CAN Network:", can_network)
    print("NAI Protocol:", nai_protocol)
    print("Bit Rate:", bit_rate)
    print("Tester ID:", tester_id)
    print("ECU ID   :", ecu_id)

    # Call can_init with hex string IDs, same as connect_to_can_bus()
    if app_comm.can_init(can_network, bit_rate, tester_id, ecu_id, nai_protocol):
        app.set_btn_enabled('CONNECT_BTN', False)
        app.show_dialog("Success", "Connected to CAN Bus successfully.")
    else:
        app.show_dialog("Error", "Failed to connect to CAN Bus. Please check the hardware or settings.")



def validate_hex_input(value):
    try:
        int(str(value), 16)  # ✅ Correct: convert value to string, then parse as hex
        return True
    except ValueError:
        return False
    
def boot_lock():
    print('app_logic : trying to lock into bootloader...')
    app_ui.append_log('trying to lock into bootloader...')

    handle = app_comm.g_pcan_handle
    config = app_comm.g_pcan_config
    if app_comm.testTesterPresent(handle, config) == False:
        print('app_logic : tester present test failed')
        app_ui.set_btn_enabled('BROWSE_BTN', True)

def upload_file():
    print('app_logic : initiating file upload...')
    app_ui.append_log('initiating file upload...')

    app_ui.set_btn_enabled('BROWSE_BTN', False)

    app_comm.perform_service_tests()

def reset_ecu():
    print('app_logic : resetting ecu...')
    app_ui.append_log('resetting ecu...')

    handle = app_comm.g_pcan_handle
    config = app_comm.g_pcan_config
    threading.Thread(target=app_comm.testECUReset, args=(handle, config)).start()
    # app_comm.testECUReset(handle, config)

# Function to handle application exit
def on_close():
    app_ui.reset_sysout()
    handle = app_comm.g_pcan_handle
    app_comm.objPCANUds.Uninitialize_2013(handle)
  #  g_ui_main_window.destroy()
    print('app_logic : destroyed ui root')
