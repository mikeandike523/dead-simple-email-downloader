from termcolor import colored

from pysrc.helpers.exchange.outlook.downloading import download_all_folders


def impl_exchange_outlook_download(reset=False):
    try:
        return download_all_folders(reset=reset)
    except KeyboardInterrupt:
        print(colored("Process aborted by user.", "red"))
        return -1
