import process_utils
import pywinhandle

pids = process_utils.get_process_ids_by_name("WeChat.exe")

pywinhandle.close_handles(
    pywinhandle.find_handles(
        pids,
        ['_WeChat_App_Instance_Identity_Mutex_Name']
    )
)