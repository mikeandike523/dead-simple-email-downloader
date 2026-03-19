from pysrc.webui.gmail_manage.server import run_server


def impl_google_gmail_manage(force_label_case: bool = False, hide_external_images: bool = False):
    """Launch the Gmail Manage web UI (Flask + Socket.IO, random port)."""
    run_server(force_label_case=force_label_case, hide_external_images=hide_external_images)
