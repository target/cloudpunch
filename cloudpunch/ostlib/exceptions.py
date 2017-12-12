class OSTLibError(Exception):

    def __init__(self, message):
        super(OSTLibError, self).__init__(message)
        self.message = message
