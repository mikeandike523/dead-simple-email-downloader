from termcolor import colored

from pysrc.helpers.outlook.outputting import export_outlook_output


def impl_outlook_output(outdir: str) -> int:
    try:
        return export_outlook_output(outdir)
    except KeyboardInterrupt:
        print(colored("Process aborted by user.", "red"))
        return -1
