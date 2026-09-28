'''
Copyright 2024-2025 Accolade Electronics Pvt. Ltd

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
version 2 as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

file        app_comm.py
brief       This is the source file for the UDS stack integration

date        01 Apr 2024
author      Accolade Electronics <www.accoladeelectronics.com>
'''

# For PCAN stack python modules
import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uds_stack'))

########################################### (UDS over CAN: core initialization) ####################################################

import threading                # for file upload thread
import time                     # for sleeping
from PCAN_UDS_2013 import *     # for UDS stack
from Crypto.Cipher import AES   # for AES encryption
import ctypes
from ctypes import create_string_buffer, byref


# A global counter to keep track of the number of failed tests (see display_uds_msg function)
g_nbErr = 0

# import the dlls required for stack
from pathlib import Path

# dll_path = Path(__file__).resolve().parent /'uds_stack'
# sys.path.insert(0, str(dll_path))
# os.add_dll_directory(str(dll_path))

# create uds library object
objPCANUds = PCAN_UDS_2013()

g_pcan_handle = PCANTP_HANDLE_USBBUS1
g_pcan_config = uds_msgconfig()

def test_result_to_string(test):
    return 'Success' if test else 'Fail'

def print_test_status(test):
    return test_result_to_string(objPCANUds.StatusIsOk_2013(test, PUDS_STATUS_OK, False))

def can_init(bit_rate, tester_id, ecu_id, iso_tp_addressing_mode):
    print(f'app_comm  : bit_rate              : {bit_rate}')
    print(f'app_comm  : tester_id             : {tester_id:X}')
    print(f'app_comm  : ecu_id                : {ecu_id:X}')
    print(f'app_comm  : iso_tp_addressing_mode: {iso_tp_addressing_mode}')

    # Print version information
    buff_size = 256
    buffer = create_string_buffer(buff_size)
    status = objPCANUds.GetValue_2013(PCANTP_HANDLE_NONEBUS, PUDS_PARAMETER_API_VERSION, buffer, buff_size)
    print('app_comm  : PCAN-UDS API Version - %s: %s' % (buffer.value, print_test_status(status)))

    # Initialize channel
    if bit_rate == '250Kbps':
        status = objPCANUds.Initialize_2013(g_pcan_handle, PCANTP_BAUDRATE_250K, 0, 0, 0)
    if bit_rate == '500Kbps':
        status = objPCANUds.Initialize_2013(g_pcan_handle, PCANTP_BAUDRATE_500K, 0, 0, 0)
    if bit_rate == '1Mbps':
        status = objPCANUds.Initialize_2013(g_pcan_handle, PCANTP_BAUDRATE_1M, 0, 0, 0)
    print('app_comm  : Initialize channel: %s' % (print_test_status(status)))

    if print_test_status(status) == 'Fail':
        return False

    # Get timeout values
    timeout_request = c_uint32(0)
    status = objPCANUds.GetValue_2013(g_pcan_handle, PUDS_PARAMETER_TIMEOUT_REQUEST, timeout_request,
                                    sizeof(timeout_request))
    print('app_comm  : Get request timeout value (%ums): %s' % (timeout_request.value, print_test_status(status)))
    customTimeOut = c_uint32(timeout_request.value * 2)
    status = objPCANUds.SetValue_2013(g_pcan_handle,
                                    PUDS_PARAMETER_TIMEOUT_REQUEST,
                                    customTimeOut, sizeof(customTimeOut))
    print('app_comm  : Set request timeout value (%ums): %s' % (customTimeOut.value, print_test_status(status)))
    status = objPCANUds.GetValue_2013(g_pcan_handle, PUDS_PARAMETER_TIMEOUT_REQUEST, timeout_request,
                                    sizeof(timeout_request))
    print('app_comm  : Get request timeout value (%ums): %s' % (timeout_request.value, print_test_status(status)))

    timeout_response = c_uint32(0)
    status = objPCANUds.GetValue_2013(g_pcan_handle, PUDS_PARAMETER_TIMEOUT_RESPONSE, timeout_response,
                                    sizeof(timeout_response))
    print('app_comm  : Get response timeout value (%ums): %s' % (timeout_response.value, print_test_status(status)))
    customTimeOut = c_uint32(timeout_response.value * 2)
    status = objPCANUds.SetValue_2013(g_pcan_handle,
                                    PUDS_PARAMETER_TIMEOUT_RESPONSE,
                                    customTimeOut, sizeof(customTimeOut))
    print('app_comm  : Set response timeout value (%ums): %s' % (customTimeOut.value, print_test_status(status)))
    status = objPCANUds.GetValue_2013(g_pcan_handle, PUDS_PARAMETER_TIMEOUT_RESPONSE, timeout_response,
                                    sizeof(timeout_response))
    print('app_comm  : Get response timeout value (%ums): %s' % (timeout_response.value, print_test_status(status)))

    # CAN-TP PRIORITY bits.
    can_tp_prio = c_uint32(0)
    status = objPCANUds.GetValue_2013(g_pcan_handle, PUDS_PARAMETER_J1939_PRIORITY, can_tp_prio,
                                    sizeof(can_tp_prio))
    print('app_comm  : Get default PUDS_PARAMETER_J1939_PRIORITY (%ums): %s' % (can_tp_prio.value, print_test_status(status)))

    # TODO: Priority bits. understand why is it required for "TCU (chetak) and GRAD". other projects may vary
    if tester_id == 0x726:
        can_tp_prio = c_uint32(3)
        status = objPCANUds.SetValue_2013(g_pcan_handle,
                                        PUDS_PARAMETER_J1939_PRIORITY,
                                        can_tp_prio, sizeof(can_tp_prio))
        print('app_comm  : New PUDS_PARAMETER_J1939_PRIORITY (%ums): %s' % (can_tp_prio.value, print_test_status(status)))

    # Add can id filter
    # Dev Note: Write DID fails if filter is not added
    status = objPCANUds.AddCanIdFilter_2013(g_pcan_handle, ecu_id)
    print('app_comm  : Add can id filter (0x%X): %s' % (ecu_id, print_test_status(status)))

    # extract the source and destination ids. ECU is UDS server and Tester is UDS client
    client_id = tester_id & 0x00000FF
    server_id = ecu_id & 0x00000FF

    # Define Network Address Information used for all the tests
    g_pcan_config.can_id = tester_id
    g_pcan_config.can_msgtype = PCANTP_CAN_MSGTYPE_EXTENDED

    # TODO: study which CAN ids requires the EXTENDED protocol, and which the NORMAL
    # The following if/else can be then done based on ID instead of
    # user defined configuration
    nai_protocol = iso_tp_addressing_mode
    if nai_protocol == '29B_EXTENDED':
        g_pcan_config.nai.protocol = PUDS_MSGPROTOCOL_ISO_15765_2_29B_EXTENDED 
    elif nai_protocol == '29B_FIXED_NORMAL':
        g_pcan_config.nai.protocol = PUDS_MSGPROTOCOL_ISO_15765_2_29B_FIXED_NORMAL
    else:
        g_pcan_config.nai.protocol = PUDS_MSGPROTOCOL_ISO_15765_2_29B_NORMAL

    g_pcan_config.nai.target_type = PCANTP_ISOTP_ADDRESSING_PHYSICAL
    g_pcan_config.type = PUDS_MSGTYPE_USDT
    g_pcan_config.nai.source_addr = client_id
    g_pcan_config.nai.target_addr = server_id

    print(f'app_comm  : PCAN initialized with bit rate {bit_rate}, server id {hex(server_id)}, client id {hex(client_id)}')
    return True

########################################### (UDS over CAN: service tests) ####################################################

g_file_path = ''
g_file_size = 0


def test_read_write_did(handle, config, did, update_did_widget):
    print(f"\nTesting DID: {hex(did)}")

    # Call testReadDataByIdentifier and process the result
    response_data, is_valid = testReadDataByIdentifier(handle, config, did)

    if response_data and is_valid:
        print(f"app_comm: Read data by ID succeeded for DID: {hex(did)}")
        print(f"Response Data for DID {hex(did)}: {response_data['response']}")

        raw_data = response_data['response'][3:]
        print(f"Processed Raw Data for DID {hex(did)}: {raw_data}")

        # Update the corresponding widget in the GUI with the ASCII data
        update_did_widget(did, raw_data)

        # Return the ASCII string
        return raw_data
    else:
        print(f"app_comm: Read data by ID test failed for DID: {hex(did)}")
        error_type = response_data.get("type", "Unknown") if response_data else "Unknown"
        print(f"Error Type: {error_type}")

    return None  # Return None if the test fails

def stopRoutine():
        # Step 1: Test Diagnostic Session Control
    handle = g_pcan_handle
    config = g_pcan_config
    if testSaveExitRoutine(handle, config) == False:
        print('Accessing session control failed')
        return




def startRoutineCert():
        # Step 1: Test Diagnostic Session Control
    handle = g_pcan_handle
    config = g_pcan_config

    # Step 1: Test Diagnostic Session Control
    if testDiagnosticSessionControl(handle, config) == False:
        print('Accessing session control failed')
        return

    # Step 2: Test Security Access
    if testSecurityAccess(handle, config) == False:
        print('Security Access failed')
        return

    if not selected_files_result:
        print("Error: No files selected. Please select files first.")
        return

    routine_result = testRoutineControlCrcCheck(handle, config, selected_files_result)

    # Check the result of the routine control test
    if routine_result:
        print("Routine Control was successful.")
    else:
        print("Routine Control failed.")


def test_write_did(did, hex_value):
    # Step 1: Convert DID from hex string to int if necessary
    if isinstance(did, str):
        try:
            did = int(did, 16)
        except ValueError:
            print(f"[ERROR] Invalid DID value '{did}', cannot convert to integer.")
            return

    # Step 2: Clean and validate hex_value
    original_input = hex_value
    hex_value = hex_value.replace(" ", "")  # Remove spaces
    try:
        int(hex_value, 16)  # Validate it's a hex string
    except ValueError:
        print(f"[ERROR] Invalid hex value '{hex_value}', must be a valid hexadecimal string.")
        return

    # Step 3: Pad hex string if length is odd
    if len(hex_value) % 2 != 0:
        hex_value = "0" + hex_value

    # Step 4: Convert to bytearray
    try:
        data_record = bytearray.fromhex(hex_value)
    except ValueError as e:
        print(f"[ERROR] Cannot convert hex to bytes: {e}")
        return

    data_record_size = len(data_record)

    # Step 5: Log all key details
    print(f"[INFO] Preparing to write DID: 0x{did:04X}")
    print(f"[INFO] Hex value to be written: {hex_value}")
    print(f"[INFO] Data record size: {data_record_size}")
    print(f"[INFO] Data record: {data_record.hex()}")

    # Step 6: DID as bytes
    try:
        did_bytes = did.to_bytes(2, byteorder='big')
        print(f"[DEBUG] Processed DID (2 bytes): {did_bytes.hex()}")
    except OverflowError:
        print(f"[ERROR] DID value {did} is too large to fit in 2 bytes.")
        return


    # Step 7: Call the write function
    try:
        response_data, is_valid = testWriteDataByIdentifier(
            g_pcan_handle,
            g_pcan_config,
            did,
            data_record,
            data_record_size
        )

        if response_data['type'] == "Negative":
            print(f"[ERROR] ECU rejected WriteDataByIdentifier request for DID 0x{did:04X}.")
            print(f"[DEBUG] Response: {response_data.get('response')}")
        else:
            print(f"[SUCCESS] WriteDataByIdentifier for DID 0x{did:04X} succeeded.")

        # Attach original input for reference
        response_data['display_value'] = original_input
        return response_data

    except Exception as e:
        print(f"[ERROR] Exception during WriteDataByIdentifier: {e}")
        return {"type": "Negative", "error": str(e)}



def testRoutineControl(channel, config):
    routine_control_option_record = create_string_buffer(2)
    routine_control_option_record_size = 2
    request = uds_msg()       # UDS message for the request
    response = uds_msg()      # UDS message for the response
    confirmation = uds_msg()  # UDS message for the confirmation
    result = False

    # Call the SvcRoutineControl_2013 function to send the message
    routine_control_option_record_size =1
    for i in range(6):
        routine_control_option_record[0] = 0x1
       
    # # Send Request Routine Results message
    status = objPCANUds.SvcRoutineControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_STR, 0xF001,
                                                routine_control_option_record, routine_control_option_record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
         status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcRoutineControl_2013 Result: %i' % (status.value))    
    print('Execute Routine Control service (Start Routine): %s' % (print_test_status(status)))
    
    # Wait for the response after sending the request
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    
    # Process the response for Start Routine
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: RoutineControl (Start Routine): ' + test_result_to_string(result))

    # Free resources
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    
    return result

def testReadDataByIdentifier(channel, config, did):

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    result = None

    print('\n\n*** UDS Service: ReadDataByIdentifier ***')

    # Wrap `did` in a ctypes object (e.g., c_uint16 for 16-bit DID)
    data_identifier = c_uint16(did)

    # Sends a physical ReadDataByIdentifier message
    status = objPCANUds.SvcReadDataByIdentifier_2013(channel, config, request, data_identifier, 1)
    
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print('UDS_SvcReadDataByIdentifier_2013: %x' % (status.value))
    
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: ReadDataByIdentifier [{}]: {}'.format(hex(did), test_result_to_string(result)))

    # Free messages
    objPCANUds.MsgFree_2013(request)
    objPCANUds.MsgFree_2013(response)
    objPCANUds.MsgFree_2013(confirmation)
    
    return result


def testControlDTCSetting(channel, config, controlParameter):
    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    result = False

    # Sends a physical ControlDTCSetting message
    print('\n\nSends a physical ControlDTCSetting message: ')
    dtc_setting_control_option_record = (c_uint8 * 1)(0x00)
    status = objPCANUds.SvcControlDTCSetting_2013(channel, config, request, controlParameter,
                                                  dtc_setting_control_option_record, 0)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcControlDTCSetting_2013: %i' % (status.value))
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: ControlDTCSetting: ' + test_result_to_string(result))

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result

# def testDiagnosticSessionControl(channel, config):
#     request = uds_msg()
#     response = uds_msg()
#     session_info = uds_sessioninfo()
#     confirmation = uds_msg()
#     status = objPCANUds.SvcDiagnosticSessionControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_DSC_ECUPS)
#     print('Execute Diagnostic Session Control service: %s' % (print_test_status(status)))
#     if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
#         status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
#     result = False
#     if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
#         result = display_uds_msg_validate(confirmation, response, False)
#     else:
#         result = display_uds_msg_validate(request, None, False)

#     print('UDS Service: DiagnosticSessionControl: ' + test_result_to_string(result))

#     status = objPCANUds.MsgFree_2013(request)
#     status = objPCANUds.MsgFree_2013(response)
#     status = objPCANUds.MsgFree_2013(confirmation)
#     return result

def testDiagnosticSessionControl(channel, config):
    request = uds_msg()
    response = uds_msg()
    session_info = uds_sessioninfo()
    confirmation = uds_msg()
    status = objPCANUds.SvcDiagnosticSessionControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_DSC_ECUPS)
    print('Execute Diagnostic Session Control service: %s' % (print_test_status(status)))
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    result = False
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: DiagnosticSessionControl: ' + test_result_to_string(result))

    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result


def aes_128_encrypt(key, security_access_data):
    # Create AES cipher object in ECB mode
    cipher = AES.new(key, AES.MODE_ECB)

    # Pad the plaintext
    #plaintext_padded = pad(security_access_data, AES.block_size)

    # Encrypt the plaintext
    ciphertext_bytes = cipher.encrypt(security_access_data)

    # Convert ciphertext to hexadecimal string
    #ciphertext_hex = binascii.hexlify(ciphertext_bytes)
    #print("ciphertext_hex:", ciphertext_hex)

    return ciphertext_bytes

def cleanup_msgs(*msgs):
    for msg in msgs:
        objPCANUds.MsgFree_2013(msg)
        
def testSecurityAccess(channel, config):
    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    security = "AES128"

    result = False
    diagnostic_session_key =bytearray(4)
    print(f"Security Access : {security}")

    # Set seed length
    seed_length = 16 if security == "AES128" else 4
    security_access_data = ctypes.create_string_buffer(seed_length)

    # Step 1: Request seed
    status = objPCANUds.SvcSecurityAccess_2013(
        channel,
        config,
        request,
        objPCANUds.PUDS_SVC_PARAM_SA_RSD_1,
        security_access_data,
        0
    )

    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print('UDS_SvcSecurityAccess_2013: %i' % (status.value))

    if not objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        _, result = display_uds_msg_validate(request, None, False)
        cleanup_msgs(request, response, confirmation)
        return {"request": request, "response": response, "type": "Negative"}, result

    # Step 2: Extract seed
    for i in range(seed_length):
        security_access_data[i] = response.msg.msgdata.any.contents.data[2 + i]

    # Step 3: Generate key based on method
    if security == "AES128":
        key = b'TCATMVCC2BLU5UEE'
        print("in test security access", key)
        diagnostic_session_key = aes_128_encrypt(key, security_access_data)
    elif security == "XOR":
        diagnostic_session_key[0] = security_access_data[0:1][0] ^ 0xAA
        diagnostic_session_key[1] = security_access_data[1:2][0] ^ 0xAA  # High byte
        diagnostic_session_key[2] = security_access_data[2:3][0] ^ 0xAA
        diagnostic_session_key[3] = security_access_data[3:4][0] ^ 0xAA
    else:
        print("Unsupported Security Method")
        cleanup_msgs(request, response, confirmation)
        return {"request": request, "response": response, "type": "Negative"}, False

    # Step 4: Write the generated key into buffer
    for i in range(seed_length):
        security_access_data[i] = diagnostic_session_key[i]

    # Step 5: Validate seed response
    _, result = display_uds_msg_validate(confirmation, response, False)
    status = objPCANUds.MsgFree_2013(request)

    status = objPCANUds.MsgFree_2013(response)

    status = objPCANUds.MsgFree_2013(confirmation)
 
    print('result :',result)
    # Step 6: Send key
    if result:
        status = objPCANUds.SvcSecurityAccess_2013(
            channel,
            config,
            request,
            objPCANUds.PUDS_SVC_PARAM_SA_SK_2,
            security_access_data,
            ctypes.sizeof(security_access_data)
        )
        if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
            status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
            print('UDS_SvcSecurityAccess_2013: %i' % (status.value))
            if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
                _, result = display_uds_msg_validate(confirmation, response, False)
            else:
                _, result = display_uds_msg_validate(request, None, False)

    print('UDS Service: SecurityAccess: ' + test_result_to_string(result))

    #cleanup_msgs(request, response, confirmation)

    return result



def testWriteDataByIdentifier(channel, config, did, data_record, data_record_size):
    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    # Ensure correct DID value is being passed into this function

    # Convert data_record (bytearray) to ctypes buffer
    data_record_ctypes = ctypes.create_string_buffer(bytes(data_record))

    # Sends a physical WriteDataByIdentifier message
    print('\n\nSends a physical WriteDataByIdentifier message: ')
    status = objPCANUds.SvcWriteDataByIdentifier_2013(channel, config, request, did, data_record_ctypes, data_record_size)

    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)

    print(f'UDS_SvcWriteDataByIdentifier_2013: {status.value}')

    result = False

    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    # Print the DID in hex (using hex() on bytes)
    #print(f'UDS Service: WriteDataByIdentifier [{did.hex()}] : {test_result_to_string(result)}')

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    return result


def testRoutineControlFlashErase(channel, config):
    routine_control_option_record = create_string_buffer(1)
    routine_control_option_record_size = 1

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    result = False

    print('\n\n*** UDS Service: RoutineControl Erasing Flash***')

    # Sends a physical RoutineControl message
    print('\n\nSends a physical RoutineControl message: ')
    for i in range(routine_control_option_record_size):
        routine_control_option_record[i] = 0x0

    status = objPCANUds.SvcRoutineControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_STR, 0x2001,
                                               routine_control_option_record, routine_control_option_record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcRoutineControl_2013 Start: %i' % (status.value))

    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    status = objPCANUds.SvcRoutineControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_STPR, 0x2001,
                                               routine_control_option_record, routine_control_option_record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcRoutineControl_2013 Stop: %i' % (status.value))

    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    status = objPCANUds.SvcRoutineControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_RRR, 0x2001,
                                               routine_control_option_record, routine_control_option_record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcRoutineControl_2013 Result: %i' % (status.value))
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: RoutineControl Erasing Flash: ' + test_result_to_string(result))

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result

def testRequestDownload(channel, config):
    memory_address_buffer = create_string_buffer(4)
    memory_size_buffer = create_string_buffer(4)
    memory_address_size = 4
    memory_size_size = 4

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    print('\n\n*** UDS Service: RequestDownload ***')

    # Sends a physical RequestDownload message
    for i in range(memory_address_size):
        memory_address_buffer[i] = 0xFF
        memory_size_buffer[i] = (g_file_size & (0x01 < i)) > i
        print(memory_size_buffer[i])
        print(' ')

    status = objPCANUds.SvcRequestDownload_2013(channel, config, request, 0x0, 0x0, memory_address_buffer,
                                                memory_address_size, memory_size_buffer,
                                                memory_size_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    result = False
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: RequestDownload: ' + test_result_to_string(result))

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result

def testTrasferFile(channel, config, file_path, file_size):
    file_transfer_thread = threading.Thread(target=transfer_file, args=(channel, config,  file_path, file_size))
    file_transfer_thread.start()

################################################## TMP START

def readFileInChunk(offset, chunk_size):
    with open(g_file_path, 'rb') as file:
        file.seek(offset)
        readChukData = file.read(chunk_size)
    return readChukData, len(readChukData)

def transfer_file(channel, config, file_path, file_size):
    print(f'transferring file {file_size} {file_path}')
    chunk_size = 254
    sequence = 0
    fileOffset = 0
    index = 0
    status = True
    while index < g_file_size - 1:
        data, read_bytes = readFileInChunk(fileOffset, chunk_size)
        print(f'Offset : {fileOffset}, read_bytes : {read_bytes}, seq : {sequence}')
        fileOffset = read_bytes + fileOffset
        update_progress_bar(file_size, fileOffset)
        index = fileOffset
        status &= testTransferData(channel, config, read_bytes, data, sequence)
        sequence = sequence + 1

def testTransferData(channel, config, size, buffer, sequence):
    record = create_string_buffer(size)
    record_size = size

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    for i in range(record_size):
        record[i] = buffer[i]

    status = objPCANUds.SvcTransferData_2013(channel, config, request, sequence, record, record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcTransferData_2013: %i' % (status.value))
    result = False
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: TransferData: [' + str(sequence) + '] :' + test_result_to_string(result))

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result

################################################## TMP END

def testRequestTransferExit(channel, config):
    record = create_string_buffer(50)
    record_size = 2

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()

    print('\n\n*** UDS Service: RequestTransferExit ***')

    for i in range(record_size):
        record[i] = 0xFF

    status = objPCANUds.SvcRequestTransferExit_2013(channel, config, request, record, record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    result = False
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: RequestTransferExit: ' + test_result_to_string(result))

    # Free messages
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)
    return result


def testRoutineControlCrcCheck(channel, config, select_files_result):

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    result = False

    print('\n\n*** UDS Service: RoutineControl Erasing Flash***')

    # Free the resources used by the first request/response
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    # Prepare for the next message (Request Routine Results)
    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    if not select_files_result:
        print("Error: No file data provided.")
        return False

    file_01_data = select_files_result["file_01_data"]
    all_files_data = select_files_result["all_files_data"]

    sequence_number_01 = int(file_01_data["sequence_number"], 16)
    crc32_value_01 = int(file_01_data["crc32"], 16)

    # Convert file sizes from hex strings to integers
    file_sizes = [int(file["file_size"], 16) for file in all_files_data]

    # Calculate total routine control option record size
    routine_control_option_record_size = 6 + (4 * len(file_sizes))  # 6 bytes header + 4 bytes per file size
    routine_control_option_record = create_string_buffer(routine_control_option_record_size)

    # Assign sequence number (1 byte)
    routine_control_option_record[0] = sequence_number_01 & 0xFF

    # Assign CRC32 (4 bytes, big-endian format)
    routine_control_option_record[1] = (crc32_value_01 >> 24) & 0xFF  # MSB first
    routine_control_option_record[2] = (crc32_value_01 >> 16) & 0xFF
    routine_control_option_record[3] = (crc32_value_01 >> 8) & 0xFF
    routine_control_option_record[4] = (crc32_value_01 >> 0) & 0xFF  # LSB last

    # Assign the number of selected files (1 byte)
    routine_control_option_record[5] = len(file_sizes) & 0xFF

    # Populate file sizes (4 bytes each, big-endian)
    offset = 6  # Start after sequence number, CRC32, and file count
    for file_size in file_sizes:
        routine_control_option_record[offset + 0] = (file_size >> 24) & 0xFF  # MSB first
        routine_control_option_record[offset + 1] = (file_size >> 16) & 0xFF
        routine_control_option_record[offset + 2] = (file_size >> 8) & 0xFF
        routine_control_option_record[offset + 3] = (file_size >> 0) & 0xFF  # LSB last
        offset += 4

    print('\n\n*** UDS Service: RoutineControl Erasing Flash***')

    # Call the UDS service
    status = objPCANUds.SvcRoutineControl_2013(
        channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_STR, 0xF001,
        routine_control_option_record, routine_control_option_record_size
    )
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        print('UDS Service call successful.')
        return True
    else:
        print('UDS Service call failed.')
        return False



def testSaveExitRoutine(channel, config):
    routine_control_option_record = create_string_buffer(2)
    routine_control_option_record_size = 2

    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    result = False

    print('\n\nSending a RoutineControl Stop message ')
    # Free the resources used by the first request/response
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    # Prepare for the next message (Request Routine Results)
    request = uds_msg()
    response = uds_msg()
    confirmation = uds_msg()
    
    routine_control_option_record_size =1
    for i in range(6):
        routine_control_option_record[0] = 0x1
       
    status = objPCANUds.SvcRoutineControl_2013(channel, config, request, objPCANUds.PUDS_SVC_PARAM_RC_STPR, 0xF102,
                                                routine_control_option_record, routine_control_option_record_size)
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
         status = objPCANUds.WaitForService_2013(channel, request, response, confirmation)
    print(' UDS_SvcRoutineControl_2013 Result: %i' % (status.value))

    # Process the response for the Routine Control result
    if objPCANUds.StatusIsOk_2013(status, PUDS_STATUS_OK, False):
        result = display_uds_msg_validate(confirmation, response, False)
    else:
        result = display_uds_msg_validate(request, None, False)

    print('UDS Service: RoutineControl Erasing Flash: ' + test_result_to_string(result))

    # Free resources used by the second request/response
    status = objPCANUds.MsgFree_2013(request)
    status = objPCANUds.MsgFree_2013(response)
    status = objPCANUds.MsgFree_2013(confirmation)

    return result

########################################### (UDS over CAN: helpers for service tests) ####################################################

def getCChar(c):
    return c if sys.version_info.major >= 3 else chr(c)

def Reverse32(v):
    res = create_string_buffer(4)
    res[3] = getCChar(v & 0x000000FF)
    res[2] = getCChar((v >> 8) & 0x000000FF)
    res[1] = getCChar((v >> 16) & 0x000000FF)
    res[0] = getCChar((v >> 24) & 0x000000FF)
    return res

def display_uds_msg_validate(request, response, no_response_expected):
    global g_nbErr
    response_data = {
        "request": None,
        "response": None,
        "type": None
    }

    if request is not None and request.msg.msgdata.isotp:
        print('\nUDS request from 0x%04X (to 0x%04X, with extension address 0x%02X) - result: %i - %s' % (
            request.msg.msgdata.isotp.contents.netaddrinfo.source_addr,
            request.msg.msgdata.isotp.contents.netaddrinfo.target_addr,
            request.msg.msgdata.isotp.contents.netaddrinfo.extension_addr,
            request.msg.msgdata.any.contents.netstatus,
            'ERROR !!!' if request.msg.msgdata.any.contents.netstatus != PCANTP_NETSTATUS_OK.value else 'OK !'))
        # Display request data
        request_data = []
        print('\t-> Length: {x1}, Data= '.format(x1=format(request.msg.msgdata.any.contents.length, 'd')), end="") 
        for i in range(request.msg.msgdata.any.contents.length):
            byte = format(request.msg.msgdata.any.contents.data[i], '02X')
            request_data.append(byte)
            print(byte, end=" ")
        print()
        response_data["request"] = request_data

    if response is not None and response.msg.msgdata.isotp:
        print('\nUDS RESPONSE from 0x%04X (to 0x%04X, with extension address 0x%02X) - result: %i - %s' % (
            response.msg.msgdata.isotp.contents.netaddrinfo.source_addr,
            response.msg.msgdata.isotp.contents.netaddrinfo.target_addr,
            response.msg.msgdata.isotp.contents.netaddrinfo.extension_addr,
            response.msg.msgdata.any.contents.netstatus,
            ('ERROR !!!' if response.msg.msgdata.any.contents.netstatus != PCANTP_NETSTATUS_OK.value else 'OK !')))

        # Display response data
        response_data_bytes = []
        print('\t-> Length: {x1}, Data= '.format(x1=format(response.msg.msgdata.any.contents.length, 'd')), end="") 
        for i in range(response.msg.msgdata.any.contents.length):
            byte = format(response.msg.msgdata.any.contents.data[i], '02X')
            response_data_bytes.append(byte)
            print(byte, end=" ")
        print()
        response_data["response"] = response_data_bytes

        # Validate response type
        respSID = request.msg.msgdata.any.contents.data[0] + 0x40
        if respSID == response.msg.msgdata.any.contents.data[0]:
            print('Positive Response')
            response_data["type"] = "Positive"
            return response_data, True
        elif 0x7F == response.msg.msgdata.any.contents.data[0]:
            print('Negative Response')
            response_data["type"] = "Negative"
            g_nbErr += 1
            return response_data, False
        else:
            print('Invalid Response')
            response_data["type"] = "Invalid"
            g_nbErr += 1
            return response_data, False

    elif not no_response_expected:
        print('\n      ERROR: NO UDS RESPONSE !!\n')
        g_nbErr += 1
        response_data["type"] = "No Response"
        return response_data, False

    return response_data, False