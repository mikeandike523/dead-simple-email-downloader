from termcolor import colored

from pysrc.helpers.exchange.outlook.outputting import export_outlook_output


def impl_exchange_outlook_output(outdir: str, max_subject_chars: int = 36) -> int:
    try:
        return export_outlook_output(outdir, max_subject_chars=max_subject_chars)
    except KeyboardInterrupt:
        print(colored("Process aborted by user.", "red"))
        return -1
