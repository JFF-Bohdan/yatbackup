import os
import logging

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_TO_CONSOLE = True

# log format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
APP_LOG_LEVEL = logging.DEBUG

