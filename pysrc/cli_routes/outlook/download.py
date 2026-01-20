from termcolor import colored

from pysrc.helpers.outlook.downloading import download_all_folders


def impl_outlook_download():
    try:
        return download_all_folders()
    except KeyboardInterrupt:
        print(colored("Process aborted by user.", "red"))
        return -1
