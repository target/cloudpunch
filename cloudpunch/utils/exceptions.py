class CPError(Exception):

    def __init__(self, message, logtype='error'):
        super(CPError, self).__init__(message)
        self.message = message
        self.logtype = logtype
