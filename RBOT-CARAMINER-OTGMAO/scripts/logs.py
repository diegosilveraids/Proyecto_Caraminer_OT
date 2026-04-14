# -*- coding: utf-8 -*-
import os

try:
    logs_path = GetVar("LOGS_PATH")
    log_type = GetVar("log_type")
    log_message = GetVar("log_message")
    log_time = GetVar("log_time")
    log_robot = GetVar("log_robot")
    log_error = GetVar("log_error")

    register_info_logs = GetVar("register_info_logs")

    if log_type not in ("INFO", "ERROR", "CRITICO"):
        raise Exception(f"El tipo de log {log_type} no es válido")

    if log_type in ("ERROR", "CRITICO"):
        new_error_log = "Time: {} | Type: {} | Robot {} | Message: {} | Error: {}\n".format(
            log_time, log_type, log_robot, log_message, log_error
        )
        error_logs_path = os.path.join(logs_path, "Error", "logs.txt")
        os.makedirs(os.path.dirname(error_logs_path), exist_ok=True)
        with open(error_logs_path, "a", encoding="utf-8") as log:
            log.write(new_error_log)

    # Comment the next if to disable 
    if register_info_logs and log_type == "INFO":
        new_info_log = "Time: {} | Type: {} | Robot: {} | Message: {}\n".format(
            log_time, log_type, log_robot, log_message
        )
        info_logs_path = os.path.join(logs_path, "Info", "logs.txt")
        os.makedirs(os.path.dirname(info_logs_path), exist_ok=True)
        with open(info_logs_path, "a", encoding="utf-8") as log:
            log.write(new_info_log)

    SetVar("log_insertion_ok", True)
except Exception as e:
    SetVar("log_insertion_ok", False)
