from pysrc.tui.gmail_manage.app import GmailManageApp


def impl_google_gmail_manage(force_label_case: bool = False):
    """Launch the Gmail Manage TUI."""
    app = GmailManageApp(force_label_case=force_label_case)
    app.run()
