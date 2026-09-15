import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from login import LoginPage
from dashboard import DashboardPage


class HSIApplication(QMainWindow):
    """
    Main application window for HSI Automation Portal.

    Flow:
        LoginPage
            ↓
        Successful Login
            ↓
        DashboardPage
            ↓
        Logout
            ↓
        LoginPage
    """

    def __init__(self):
        super().__init__()

        # =========================================================
        # WINDOW CONFIGURATION
        # =========================================================

        self.setWindowTitle(
            "HSI Automation Portal"
        )

        self.resize(
            1347,
            758
        )

        self.setMinimumSize(
            1100,
            620
        )

        # =========================================================
        # PAGE REFERENCES
        # =========================================================

        self.login_page = None
        self.dashboard = None

        # =========================================================
        # SHOW LOGIN PAGE
        # =========================================================

        self.show_login()

    # =============================================================
    # SHOW LOGIN PAGE
    # =============================================================

    def show_login(self):
        """
        Display the Login page.

        This method is also used as the logout callback
        from the Dashboard.
        """

        # ---------------------------------------------------------
        # Remove Dashboard
        # ---------------------------------------------------------

        if self.dashboard is not None:

            self.dashboard.deleteLater()

            self.dashboard = None

        # ---------------------------------------------------------
        # Remove Existing Login Page
        # ---------------------------------------------------------

        if self.login_page is not None:

            self.login_page.deleteLater()

            self.login_page = None

        # ---------------------------------------------------------
        # Create New Login Page
        # ---------------------------------------------------------

        self.login_page = LoginPage(
            self,
            self.login_success
        )

        # ---------------------------------------------------------
        # Set Login Page as Central Widget
        # ---------------------------------------------------------

        self.setCentralWidget(
            self.login_page
        )

    # =============================================================
    # LOGIN SUCCESS
    # =============================================================

    def login_success(self, user):
        """
        Called after successful login.

        Parameters
        ----------
        user:
            Logged-in user information received from LoginPage.
        """

        print(
            "Logged in:",
            user
        )

        # ---------------------------------------------------------
        # Remove Login Page
        # ---------------------------------------------------------

        if self.login_page is not None:

            self.login_page.deleteLater()

            self.login_page = None

        # ---------------------------------------------------------
        # Create Dashboard
        # ---------------------------------------------------------

        self.dashboard = DashboardPage(
            self,
            user,
            self.show_login
        )

        # ---------------------------------------------------------
        # Set Dashboard as Central Widget
        # ---------------------------------------------------------

        self.setCentralWidget(
            self.dashboard
        )

    # =============================================================
    # CLOSE EVENT
    # =============================================================

    def closeEvent(self, event):
        """
        Cleanly close the application.
        """

        # ---------------------------------------------------------
        # Clean Dashboard
        # ---------------------------------------------------------

        if self.dashboard is not None:

            try:
                self.dashboard.deleteLater()
            except Exception:
                pass

            self.dashboard = None

        # ---------------------------------------------------------
        # Clean Login Page
        # ---------------------------------------------------------

        if self.login_page is not None:

            try:
                self.login_page.deleteLater()
            except Exception:
                pass

            self.login_page = None

        # ---------------------------------------------------------
        # Accept Close Event
        # ---------------------------------------------------------

        event.accept()


# ================================================================
# APPLICATION ENTRY POINT
# ================================================================

def main():
    """
    Start the HSI Automation Portal application.
    """

    # ------------------------------------------------------------
    # Create QApplication
    # ------------------------------------------------------------

    app = QApplication(
        sys.argv
    )

    # ------------------------------------------------------------
    # Application Style
    # ------------------------------------------------------------

    app.setStyle(
        "Fusion"
    )

    # ------------------------------------------------------------
    # Create Main Window
    # ------------------------------------------------------------

    window = HSIApplication()

    # ------------------------------------------------------------
    # Show Main Window
    # ------------------------------------------------------------

    window.show()

    # ------------------------------------------------------------
    # Start Qt Event Loop
    # ------------------------------------------------------------

    return app.exec()


# ================================================================
# RUN APPLICATION
# ================================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )