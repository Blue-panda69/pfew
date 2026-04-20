from django.apps import AppConfig
import sys
import threading
import time


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Initialize background campaign scheduler when Django starts."""
        # Only start scheduler if we're running the actual server (not in migrations or management commands)
        if 'runserver' in sys.argv or 'runserver_plus' in sys.argv:
            # Try to use APScheduler first (if installed)
            if self._try_apscheduler():
                return
            
            # Fallback to threading
            self._start_threading_scheduler()

    def _try_apscheduler(self):
        """Try to use APScheduler if available. Returns True if successful."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            from django_apscheduler.jobstores import DjangoJobStore
            from django_apscheduler.util import close_old_connections
            
            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), "default")

            # Schedule the campaign sending job to run every 10 seconds
            @scheduler.scheduled_job(
                IntervalTrigger(seconds=10),
                id='send_pending_campaigns',
                name='Send pending campaigns',
                replace_existing=True,
            )
            def send_pending_campaigns_job():
                close_old_connections()
                from .tasks import send_pending_campaigns_task
                send_pending_campaigns_task()

            # Only start the scheduler if it's not already running
            if not scheduler.running:
                scheduler.start()
                print("✓ Campaign scheduler started (APScheduler, checking every 10 seconds)")
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"⚠️  APScheduler unavailable: {e}")
            return False

    def _start_threading_scheduler(self):
        """Fallback: Use threading for background campaign checks."""
        def background_campaign_check():
            """Run in background thread."""
            try:
                from .tasks import send_pending_campaigns_task
                import django
                
                while True:
                    try:
                        # Ensure Django is ready
                        if not django.apps.apps.ready:
                            time.sleep(1)
                            continue
                        
                        send_pending_campaigns_task()
                    except Exception as e:
                        print(f"⚠️  Campaign check error: {e}")
                    
                    time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"⚠️  Background scheduler error: {e}")

        # Start background thread (daemon so it stops with main thread)
        thread = threading.Thread(target=background_campaign_check, daemon=True)
        thread.start()
        print("✓ Campaign scheduler started (Threading, checking every 10 seconds)")
