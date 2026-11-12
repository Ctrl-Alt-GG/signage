import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
accesslog = "-"
errorlog = "-"
# The control socket would be created in the working directory, which is read-only.
control_socket_disable = True
