import sys
import threading

from PyQt6.QtWidgets import QApplication, QMainWindow

from login import LoginPage
from dashboard import DashboardPage

# =============================================================
# EXCEL PREPARATION SCHEDULER
# =============================================================

from excelprepare import run_scheduler


class HSIApplication(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("HSI Automation Portal")

        self.resize(1347, 758)

        self.setMinimumSize(1100, 620)

        # =====================================================
        # PAGE REFERENCES
        # =====================================================

        self.login_page = None
        self.dashboard = None

        # =====================================================
        # EXCEL PREPARATION SCHEDULER
        #
        # Starts automatically when application starts.
        #
        # Excel preparation:
        #   - Runs immediately
        #   - Checks DB
        #   - Creates Pending CSV when new data exists
        #   - Waits 20 minutes
        #   - Runs again
        #
        # It runs independently from Login/Dashboard.
        # =====================================================

        self.excel_scheduler_thread = None

        self.start_excel_scheduler()

        # =====================================================
        # SHOW LOGIN
        # =====================================================

        self.show_login()

    # =============================================================
    # START EXCEL PREPARATION
    # =============================================================

    def start_excel_scheduler(self):

        try:

            # Prevent accidental duplicate scheduler threads
            if (
                self.excel_scheduler_thread is not None
                and self.excel_scheduler_thread.is_alive()
            ):
                print(
                    "Excel preparation scheduler is already running."
                )
                return

            print(
                "=============================================="
            )

            print(
                "STARTING EXCEL PREPARATION SCHEDULER"
            )

            print(
                "=============================================="
            )

            self.excel_scheduler_thread = threading.Thread(
                target=self.run_excel_scheduler,
                name="ExcelPreparationScheduler",
                daemon=True
            )

            self.excel_scheduler_thread.start()

            print(
                "Excel preparation scheduler started."
            )

        except Exception as error:

            print(
                "Excel scheduler start error:",
                repr(error)
            )

    # =============================================================
    # EXCEL SCHEDULER THREAD
    # =============================================================

    @staticmethod
    def run_excel_scheduler():

        try:

            print(
                "Excel preparation background thread started."
            )

            # This function already handles:
            #
            # 1. Immediate execution
            # 2. DB checking
            # 3. CSV creation
            # 4. Duplicate protection
            # 5. 20-minute interval
            #
            run_scheduler()

        except Exception as error:

            print(
                "Excel preparation scheduler error:",
                repr(error)
            )

    # =============================================================
    # LOGIN
    # =============================================================

    def show_login(self):

        # ---------------------------------------------------------
        # CLOSE EXISTING DASHBOARD
        # ---------------------------------------------------------

        if self.dashboard is not None:

            try:

                self.dashboard.close_automation()

            except Exception as error:

                print(
                    "Dashboard automation cleanup error:",
                    repr(error)
                )

            try:

                self.dashboard.deleteLater()

            except Exception:
                pass

            self.dashboard = None

        # ---------------------------------------------------------
        # REMOVE EXISTING LOGIN PAGE
        # ---------------------------------------------------------

        if self.login_page is not None:

            try:

                self.login_page.deleteLater()

            except Exception:
                pass

            self.login_page = None

        # ---------------------------------------------------------
        # CREATE LOGIN PAGE
        # ---------------------------------------------------------

        self.login_page = LoginPage(
            self,
            self.login_success
        )

        self.setCentralWidget(
            self.login_page
        )

    # =============================================================
    # LOGIN SUCCESS
    # =============================================================

    def login_success(self, user):

        print(
            "Logged in:",
            user
        )

        # ---------------------------------------------------------
        # REMOVE LOGIN PAGE
        # ---------------------------------------------------------

        if self.login_page is not None:

            try:

                self.login_page.deleteLater()

            except Exception:
                pass

            self.login_page = None

        # ---------------------------------------------------------
        # CREATE DASHBOARD
        # ---------------------------------------------------------

        self.dashboard = DashboardPage(
            self,
            user,
            self.show_login
        )

        self.setCentralWidget(
            self.dashboard
        )

    # =============================================================
    # CLOSE APPLICATION
    # =============================================================

    def closeEvent(self, event):

        print(
            "Closing HSI Automation Portal..."
        )

        # ---------------------------------------------------------
        # CLOSE DASHBOARD AUTOMATION
        # ---------------------------------------------------------

        if self.dashboard is not None:

            try:

                self.dashboard.close_automation()

            except Exception as error:

                print(
                    "Automation cleanup error:",
                    repr(error)
                )

            try:

                self.dashboard.deleteLater()

            except Exception:
                pass

            self.dashboard = None

        # ---------------------------------------------------------
        # CLEAN LOGIN PAGE
        # ---------------------------------------------------------

        if self.login_page is not None:

            try:

                self.login_page.deleteLater()

            except Exception:
                pass

            self.login_page = None

        # ---------------------------------------------------------
        # EXCEL SCHEDULER
        #
        # The Excel scheduler is a daemon thread.
        # It will automatically stop when the main EXE exits.
        # ---------------------------------------------------------

        if self.excel_scheduler_thread is not None:

            print(
                "Excel preparation scheduler will stop "
                "with the application."
            )

        event.accept()


# =============================================================
# APPLICATION ENTRY POINT
# =============================================================

def main():

    print(
        "=============================================="
    )

    print(
        "HSI AUTOMATION PORTAL"
    )

    print(
        "=============================================="
    )

    app = QApplication(sys.argv)

    app.setStyle(
        "Fusion"
    )

    window = HSIApplication()

    window.show()

    return app.exec()


# =============================================================
# RUN
# =============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )