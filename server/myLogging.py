'''The tornado guys use the logging module. I'm trying to make it work with syslog, which it
says it should but I can't get it to go so I found this handler on the web and adapted it.'''

import logging
import syslog

class SysLogLibHandler(logging.Handler):
    """A logging handler that emits messages to syslog.syslog."""
    priority_map = {
        logging.DEBUG: syslog.LOG_DEBUG, 
        logging.INFO: syslog.LOG_INFO, 
        logging.WARNING: syslog.LOG_WARNING, 
        logging.ERROR: syslog.LOG_ERR, 
        logging.CRITICAL: syslog.LOG_CRIT, 
        0: syslog.LOG_NOTICE, 
        }

    def __init__(self, facility, ident):
        syslog.openlog(ident)
        self.facility = facility
        logging.Handler.__init__(self)

    def emit(self, record):
        syslog.syslog(self.facility | self.priority_map[record.levelno],
                      self.format(record))

levels = {
    'info': logging.INFO,
    'warning': logging.WARNING,
    'debug': logging.DEBUG,
    'error': logging.ERROR }
    
def init(identity, level):
    if level not in levels:
        raise 'bad logging level %s' % level
    log = logging.getLogger()
    handler = SysLogLibHandler(syslog.LOG_LOCAL0, identity)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)

    log.setLevel(levels[level])

if __name__ == '__main__':
    init('testing', 'info')
    logging.info('testing')

