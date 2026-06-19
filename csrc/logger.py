"""A simple logger implementation."""

import sys
import time


class SimpleLogger:
    """A simple logger that writes messages to a stream or file."""

    def __init__(self, filename=None, stream=sys.stderr):
        self.stream = stream
        self.filename = filename
        if filename:
            self.file = open(filename, 'a', encoding='utf-8')
        else:
            self.file = None

    def log(self, level, message):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        formatted = f"[{timestamp}] {level}: {message}
"
        self.stream.write(formatted)
        self.stream.flush()
        if self.file:
            self.file.write(formatted)
            self.file.flush()

    def info(self, message):
        self.log('INFO', message)

    def warning(self, message):
        self.log('WARNING', message)

    def error(self, message):
        self.log('ERROR', message)

    def debug(self, message):
        self.log('DEBUG', message)

    def close(self):
        if self.file:
            self.file.close()